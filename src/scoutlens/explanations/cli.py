"""Generate one grounded explanation, locally, with or without a model.

    uv run --frozen python -m scoutlens.explanations.cli explain --profile wy-8287-c-795

That command works on a clean clone with no credential, no network and no
model. It is the whole demo: a published profile goes in, a validated
explanation comes out, and every number in it can be traced to the artifact it
was copied from.

**The default explainer is not a model, and the output says so.** `deterministic`
builds the explanation the bundle supports, directly from the bundle. That is
worth having for its own sake — it proves the contract is *satisfiable*, which
a validator alone cannot tell you, since a validator that rejected everything
would look identical to a strict one. It also sets the bar: a model is not
being asked to do something no program can do, it is being asked to say the
same things better, and it is held to exactly the same validator.

**Offline is enforced, not promised.** Without `--online` the process refuses to
open a socket at all: the guard is installed around the adapter call, so an
adapter that tries to reach a network fails with a clear error instead of
quietly succeeding. "The default path is offline" is then a property of this
file rather than a claim about intent.

**A refused explanation is never shown as one.** If the adapter fails, or its
answer does not match the schema, or the validator rejects it, the command
returns the typed deterministic fallback and a non-zero exit code. The
unvalidated text is never printed, never written and never persisted — it is
the one thing this tool exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scoutlens.console import use_utf8_output
from scoutlens.explanations.adapters.conformance import load_adapter, run_conformance
from scoutlens.explanations.adapters.protocol import (
    ADAPTER_PROTOCOL_VERSION,
    AdapterFailure,
    AdapterRequest,
    AdapterResponse,
    AdapterResult,
    AdapterUsage,
    FailureReason,
)
from scoutlens.explanations.artifacts import ShowcaseArtifacts, ShowcaseUnavailable
from scoutlens.explanations.bundle import BundleError, BundleOptions, build_bundle
from scoutlens.explanations.evals.fallback import (
    Fallback,
    FallbackReason,
    deterministic_fallback,
)
from scoutlens.explanations.evals.responses import NoSuchEvidence, reference_output
from scoutlens.explanations.policy import OUTPUT_SCHEMA_VERSION
from scoutlens.explanations.prompt import PROMPT_CONTRACT_VERSION, prompt_contract
from scoutlens.explanations.schema import validate_output_schema
from scoutlens.explanations.validator import validate_output

EXIT_OK = 0
EXIT_FALLBACK = 1
EXIT_UNAVAILABLE = 2
EXIT_USAGE = 3
EXIT_OFFLINE_VIOLATION = 4

#: The only place a credential is ever read from.
#:
#: Never a command-line argument: arguments land in shell history, in `ps`
#: output and in CI logs, and a secret that has been in any of those is a
#: secret that has to be rotated.
CREDENTIAL_ENV_VAR = "SCOUTLENS_MODEL_API_KEY"


class OfflineViolation(RuntimeError):
    """Something tried to open a socket on the offline path."""


class UnknownProfile(ValueError):
    """The payload is hydrated and that profile key is not in it.

    Separate from `ShowcaseUnavailable` because the remedies have nothing in
    common. Telling someone to hydrate a payload they already have, because
    they mistyped a key, sends them to re-download 23 MB and learn nothing.
    """


@contextmanager
def offline_guard() -> Iterator[None]:
    """Refuse every outbound connection for the duration of the block.

    Blunt on purpose. A narrower guard would have to know which library an
    adapter uses to reach the network, and the whole point of a provider-neutral
    adapter boundary is that this package does not know that.
    """
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def refuse(*args: object, **kwargs: object) -> None:
        raise OfflineViolation(
            "this adapter tried to open a network connection on the offline path. "
            "Pass --online to allow it, and see `--help` for what that implies."
        )

    socket.socket.connect = refuse  # type: ignore[method-assign, assignment]
    socket.create_connection = refuse  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket.connect = real_connect  # type: ignore[method-assign]
        socket.create_connection = real_create


@dataclass
class DeterministicExplainer:
    """Builds the explanation the bundle supports. No model, and it says so.

    An adapter by shape, so the CLI has one code path and the validator is
    applied to this exactly as it is applied to a model. An explainer exempted
    from validation would be the one unchecked route in the tool.
    """

    bundle: dict[str, Any]
    adapter_version: str = "1.0.0"

    @property
    def adapter_id(self) -> str:
        return "deterministic"

    @property
    def model_id(self) -> str:
        return "none"

    def complete(self, request: AdapterRequest) -> AdapterResult:
        try:
            content = reference_output(self.bundle)
        except NoSuchEvidence as error:
            # A bundle with no weighted evidence supports no explanation, and
            # saying so as a typed failure keeps this on the same path a model's
            # failure takes: the fallback, not a crash.
            return AdapterFailure(
                reason=FailureReason.INVALID_RESPONSE,
                detail=str(error),
                adapter_id=self.adapter_id,
                model_id=self.model_id,
            )
        return AdapterResponse(
            content=content,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            model_id=self.model_id,
            usage=AdapterUsage(latency_ms=0.0),
            protocol_version=ADAPTER_PROTOCOL_VERSION,
        )


@dataclass(frozen=True)
class ExplanationResult:
    """What the command produced, and everything needed to audit it."""

    status: str
    explanation: dict[str, Any]
    provenance: dict[str, Any]
    telemetry: dict[str, Any] | None = None
    fallback_reason: str | None = None
    rejections: tuple[str, ...] = ()

    def as_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "status": self.status,
            "provenance": self.provenance,
            "explanation": self.explanation,
        }
        if self.telemetry is not None:
            record["telemetry"] = self.telemetry
        if self.fallback_reason is not None:
            record["fallback_reason"] = self.fallback_reason
            record["rejected_rules"] = list(self.rejections)
        return record


def _provenance(bundle: dict[str, Any], adapter: Any, dataset_version: str) -> dict[str, Any]:
    """Everything AC5 requires, and no endpoint or credential.

    `bundle_digest` is the evidence hash: it names the exact evidence the
    explanation answered, so an output cannot be checked against a bundle it
    never saw.
    """
    provenance = bundle["provenance"]
    return {
        "profile_key": bundle["profile_key"],
        "dataset_version": dataset_version,
        "representation_id": provenance.get("representation_id"),
        "ranking_method": provenance.get("ranking_method"),
        "is_audit_baseline_bundle": provenance.get("is_audit_baseline_bundle", False),
        "bundle_digest": bundle["bundle_digest"],
        "prompt_contract_version": PROMPT_CONTRACT_VERSION,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "adapter_protocol_version": ADAPTER_PROTOCOL_VERSION,
        "adapter_id": adapter.adapter_id,
        "adapter_version": adapter.adapter_version,
        "model_id": adapter.model_id,
    }


def _fallback_result(
    bundle: dict[str, Any],
    adapter: Any,
    dataset_version: str,
    fallback: Fallback,
    rejections: tuple[str, ...] = (),
) -> ExplanationResult:
    return ExplanationResult(
        status="fallback",
        explanation=fallback.output,
        provenance=_provenance(bundle, adapter, dataset_version),
        fallback_reason=str(fallback.reason),
        rejections=rejections,
    )


def explain(
    bundle: dict[str, Any],
    adapter: Any,
    *,
    dataset_version: str,
    online: bool = False,
) -> ExplanationResult:
    """Ask ``adapter`` for an explanation of ``bundle``, and refuse a bad one.

    The only place the two paths differ is whether the socket guard is
    installed. Everything after the adapter call — schema, validator, fallback —
    is identical, which is what makes a live run comparable to an offline one.
    """
    contract = prompt_contract(bundle)
    request = AdapterRequest(
        system=contract["system"],
        user=contract["user"],
        bundle_digest=contract["bundle_digest"],
        prompt_contract_version=contract["version"],
        schema_version=OUTPUT_SCHEMA_VERSION,
    )

    if online:
        result = adapter.complete(request)
    else:
        with offline_guard():
            result = adapter.complete(request)

    if isinstance(result, AdapterFailure):
        return _fallback_result(
            bundle,
            adapter,
            dataset_version,
            deterministic_fallback(
                bundle, reason=FallbackReason.ADAPTER_FAILURE, detail=str(result)
            ),
        )

    try:
        validate_output_schema(result.content)
    except ValueError as error:
        return _fallback_result(
            bundle,
            adapter,
            dataset_version,
            deterministic_fallback(
                bundle, reason=FallbackReason.SCHEMA_INVALID, detail=str(error)[:200]
            ),
        )

    validation = validate_output(result.content, bundle)
    if not validation.accepted:
        return _fallback_result(
            bundle,
            adapter,
            dataset_version,
            deterministic_fallback(
                bundle,
                reason=FallbackReason.VALIDATION_REJECTED,
                detail=f"refused by {len(validation.rejections)} rule(s)",
            ),
            rejections=tuple(sorted(validation.rules())),
        )

    return ExplanationResult(
        status="validated",
        explanation=result.content,
        provenance=_provenance(bundle, adapter, dataset_version),
        telemetry=result.telemetry(),
    )


#: How the retrieval score is named in rendered text.
#:
#: Never "confidence" and never bare "cosine". A similarity is a distance under
#: a fitted representation; a confidence would be a statement about how sure the
#: system is, which this study never estimates, and unweighted cosine is the
#: audit baseline rather than the published score (`D045`, `D047`, `D049`).
SIMILARITY_LABEL = "similarity score"


def render_text(result: ExplanationResult) -> str:
    """A readable rendering that repeats none of the traps the validator blocks."""
    provenance = result.provenance
    lines = [
        f"profile        {provenance['profile_key']}",
        f"status         {result.status}",
        f"representation {provenance['representation_id'] or '(v1 audit baseline)'}",
        f"method         {provenance['ranking_method']}",
        f"evidence hash  {provenance['bundle_digest']}",
        f"adapter        {provenance['adapter_id']}/{provenance['adapter_version']}"
        f" model={provenance['model_id']}",
        f"versions       prompt {provenance['prompt_contract_version']},"
        f" schema {provenance['output_schema_version']}",
    ]

    if result.fallback_reason:
        lines.append(f"fallback       {result.fallback_reason}")
        if result.rejections:
            lines.append(f"rejected by    {', '.join(result.rejections)}")

    lines.append("")
    for claim in result.explanation.get("claims", ()):
        lines.append(f"[{claim['surface']}] {claim['text']}")
        for reference in claim.get("values", ()) or ():
            label = SIMILARITY_LABEL if reference["field"] == "similarity_score" else reference["field"]
            lines.append(f"    {label} = {reference['value']}")
        lines.append(f"    evidence: {', '.join(claim['evidence_ids'])}")

    caveats = result.explanation.get("caveat_codes") or ()
    if caveats:
        lines.append("")
        lines.append("caveats        " + ", ".join(caveats))

    if provenance["adapter_id"] == "deterministic":
        lines.append("")
        lines.append(
            "No model produced this text. It was built from the published bundle, and it "
            "is what the contract permits rather than what a model happened to say."
        )
    return "\n".join(lines)


def _load_profile(artifacts: ShowcaseArtifacts, profile_key: str, *, major: int) -> dict[str, Any]:
    try:
        return artifacts.profile(profile_key, major=major)
    except ShowcaseUnavailable:
        if artifacts.available():
            raise UnknownProfile(
                f"no published v{major} profile {profile_key!r}. "
                "Run the `profiles` subcommand to see some valid keys."
            ) from None
        raise


def _build_bundle(
    artifacts: ShowcaseArtifacts, profile_key: str, *, audit_baseline: bool
) -> dict[str, Any]:
    if audit_baseline:
        # `jtt.6.1` refuses a v1 profile that was not explicitly asked for, so
        # this flag is the only route to v1 and the demo cannot reach it by
        # accident.
        profile = _load_profile(artifacts, profile_key, major=1)
        return build_bundle(profile, options=BundleOptions(audit_baseline=True))
    return build_bundle(
        _load_profile(artifacts, profile_key, major=2), artifacts.representation()
    )


def _resolve_adapter(spec: str | None, bundle: dict[str, Any]) -> Any:
    if spec is None:
        return DeterministicExplainer(bundle=bundle)
    return load_adapter(spec)


def _add_explain_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", required=True, help="a published profile key, e.g. wy-8287-c-795")
    parser.add_argument(
        "--adapter",
        help=(
            "module:factory returning your adapter, e.g. mypackage.myadapter:build. "
            "Omit it for the offline deterministic explainer."
        ),
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help=(
            "allow the adapter to open network connections. Off by default, and enforced: "
            f"without it a socket attempt fails. Credentials are read only from "
            f"${CREDENTIAL_ENV_VAR}, never from an argument."
        ),
    )
    parser.add_argument(
        "--audit-baseline",
        action="store_true",
        help="explain the frozen v1 cosine baseline instead of the v2 representation.",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--output", type=Path, help="write the JSON record here instead of stdout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scoutlens.explanations.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Offline workflow, from a clean clone:\n"
            "  uv run --frozen python -m scoutlens.showcase.payload hydrate\n"
            "  uv run --frozen python -m scoutlens.explanations.cli explain "
            "--profile wy-8287-c-795\n"
            "\n"
            "Your own model:\n"
            "  uv run --frozen python -m scoutlens.explanations.cli conformance "
            "--adapter mypackage.myadapter:build\n"
            "  uv run --frozen python -m scoutlens.explanations.cli explain "
            "--profile wy-8287-c-795 --adapter mypackage.myadapter:build --online\n"
            "\n"
            "--adapter takes module:factory - an importable module, and a zero-argument\n"
            "factory in it that returns your adapter. A factory rather than a class so\n"
            "construction stays yours: your adapter may need a client, a local path or an\n"
            "endpoint, and this tool has no business guessing.\n"
            "\n"
            "An adapter is any object with adapter_id, adapter_version, model_id and\n"
            "complete(request). See docs/ai-adapter-guide.md. The shipped reference is\n"
            "scoutlens.explanations.adapters.openai_compat:OpenAICompatibleAdapter, which\n"
            "speaks the OpenAI-compatible wire format to any base_url you configure -\n"
            "llama.cpp, vLLM, Ollama or a hosted service - with no provider SDK.\n"
            "\n"
            "Nothing reaches a network unless you pass --online, and that is enforced\n"
            "rather than promised: on the default path a socket attempt fails. If your\n"
            f"endpoint needs a credential, export ${CREDENTIAL_ENV_VAR} - it is never\n"
            "a command-line argument, because arguments land in shell history, in ps\n"
            "output and in CI logs.\n"
            "\n"
            "Exit codes: 0 validated, 1 fallback returned, 2 artifacts missing,\n"
            "3 usage error, 4 an adapter tried to reach the network while offline.\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    explain_parser = subparsers.add_parser(
        "explain", help="explain one published profile", description="Explain one profile."
    )
    _add_explain_arguments(explain_parser)

    conformance_parser = subparsers.add_parser(
        "conformance",
        help="check an adapter against the contract",
        description=(
            "Drive an adapter with synthetic requests and report whether it obeys the "
            "boundary. Never calls a real model, so it is safe with no credential."
        ),
    )
    conformance_parser.add_argument("--adapter", required=True, help="module:factory")

    subparsers.add_parser(
        "profiles", help="list a few published profile keys to try"
    ).add_argument("--limit", type=int, default=10)

    return parser


def _run_explain(args: argparse.Namespace) -> int:
    artifacts = ShowcaseArtifacts()
    bundle = _build_bundle(artifacts, args.profile, audit_baseline=args.audit_baseline)
    adapter = _resolve_adapter(args.adapter, bundle)

    try:
        result = explain(
            bundle,
            adapter,
            dataset_version=artifacts.dataset_version(),
            online=args.online,
        )
    except OfflineViolation as error:
        print(f"{error}", file=sys.stderr)
        return EXIT_OFFLINE_VIOLATION

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result.as_record(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.output}")
    elif args.format == "json":
        print(json.dumps(result.as_record(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_text(result))

    if result.status != "validated":
        print(
            f"\nThe generated explanation was not accepted ({result.fallback_reason}). "
            "What you see above is the deterministic fallback; the refused output was "
            "not shown and was not saved.",
            file=sys.stderr,
        )
        return EXIT_FALLBACK
    return EXIT_OK


def _run_conformance(args: argparse.Namespace) -> int:
    results = run_conformance(load_adapter(args.adapter))
    for result in results:
        print(result)
    failed = [result for result in results if not result.passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return EXIT_USAGE if failed else EXIT_OK


def _run_profiles(args: argparse.Namespace) -> int:
    artifacts = ShowcaseArtifacts()
    for entry in artifacts.index()[: max(args.limit, 0)]:
        print(f"{entry['profile_key']:<20} {entry['role']:<12} {entry['display_name']}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    use_utf8_output()
    args = build_parser().parse_args(argv)
    try:
        if args.command == "explain":
            return _run_explain(args)
        if args.command == "conformance":
            return _run_conformance(args)
        return _run_profiles(args)
    except ShowcaseUnavailable as error:
        print(f"cannot run: {error}", file=sys.stderr)
        return EXIT_UNAVAILABLE
    except UnknownProfile as error:
        print(f"{error}", file=sys.stderr)
        return EXIT_USAGE
    except BundleError as error:
        print(f"cannot build a bundle for that profile: {error}", file=sys.stderr)
        return EXIT_USAGE
    except SystemExit as error:  # `load_adapter` raises this for a bad spec
        print(f"{error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

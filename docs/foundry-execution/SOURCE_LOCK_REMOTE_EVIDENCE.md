# Source Lock: live remote evidence

`tools/foundry/source_lock.py` remains the sole mechanism changed here. Its
existing LOCK_OK/LOCK_FAIL CLI and 0/1 exit contract remain intact. No second
publication checker is introduced.

- Repository identity is exact GitHub owner/repository identity. HTTPS, standard
  git@github.com scp-style SSH, and ssh://git@github.com URLs are supported, with
  optional .git suffix and default ports. Credentials in HTTPS URLs, nondefault
  hosts/ports, dot segments, lookalikes and ambiguous multi-URL configurations fail.
- The legacy `--repo commander-playtest-lab` means the full canonical CPL slug.
  Other abbreviated repository fragments are no longer accepted.
- Primary `verify()` (and therefore the `bootstrap.py` source-lock gate, which
  calls `verify()` without a remote probe) rejects effective `url.*.insteadOf`
  rewrites — local, global, or environment-provided — with EFFECTIVE_URL_REWRITE.
  A canonical literal `remote.origin.url` never yields LOCK_OK/BOOTSTRAP_PASS
  while a rewrite (or unreadable rewrite configuration) is active. Omission of
  `--check-remote-ref` still means no required live remote probe.
- `--check-remote-ref topic` means refs/heads/topic; tags require refs/tags/name.
  Empty/pattern/invalid refs fail. Omission still means no required remote probe.
- A successful query requires exactly one nonzero SHA-1 OID/TAB/exact-ref record.
  Missing exact ref is ABSENT only after Git's conclusive empty-output status 2.
  Failed/undecodable/malformed/ambiguous evidence is REMOTE_REF_UNKNOWN. Neither
  condition can produce LOCK_OK. Local tracking refs are never substituted.
- Live checks reject any active url.*.insteadOf setting before and after probing.
  The check consumes only Git's exit status and discards config output; it does
  not read credential values. HTTP redirects are disabled. A validated literal
  URL is used so a changed remote-name mapping cannot silently change the target.
- Ordinary credential-helper configuration, askpass and SSH-agent environment
  remain available. No auth values are logged. Users with URL rewrites receive
  UNKNOWN, including benign rewrites; the tool never edits their configuration.
- Each Git subprocess has a 30-second timeout. Diagnostics suppress raw stderr
  and URLs that could contain credentials. Multiple bounded commands are required;
  the entire CLI is not advertised as a single 30-second operation.

Trust prerequisites: a trusted Git installation, credential helpers, SSH/TLS and
host network configuration, and stable local Git configuration during a probe.
Before/after rewrite checks detect persistent changes; they do not defeat a
hostile concurrent actor inserting then removing configuration between checks.
This is not a host sandbox, executable qualification, atomic remote reservation,
or cryptographic proof of server identity beyond the configured transport trust.

Remote presence/absence says nothing about local workstream liveness or ownership.
This change adds no TREE, writer-lock, qualification, provider or Rules authority.

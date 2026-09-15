# WS221 Manifest Negative (S4)

- test_manifest_mismatch_is_rejected (tests/qualification/test_ws221_evidence_vocab.py):
  sealed bytes → recorded digest verifies; tampered bytes → digest mismatch.
  Tampering still fails; nothing was normalized away.
- The pre-existing RED test itself is the standing mismatch detector over all
  seal-covered bytes; it is green only when bytes and manifests agree exactly.

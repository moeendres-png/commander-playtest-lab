package org.commanderlab.xmage;

import org.junit.jupiter.api.Test;

import java.nio.file.Path;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * WS60 XMage RQ-C3 first-wave execution: all 15 corrected scenarios as
 * actual-card runtime qualifications on the WS56-qualified XMage successor.
 */
class Ws60Rqc3FirstWaveTest {

    private static final Path EVIDENCE_DIR = Path.of("ws60-evidence");

    private static void runAndSeal(Ws60Suite.Spec spec, int maxAttempts) throws Exception {
        Ws60Suite.SuiteResult result = Ws60Suite.execute(spec, maxAttempts);
        Ws60Suite.writeEvidence(result, EVIDENCE_DIR);
        System.out.println("WS60 " + spec.shortId() + " verdict=" + result.verdict()
                + " attempts=" + result.attempts().size()
                + " primary_seed=" + result.primary().seed()
                + " decisions=" + result.primary().decisionsAnswered()
                + " replica_stopped=" + result.replica().stoppedReason()
                + " replica_decisions=" + result.replica().decisionsAnswered()
                + " determinism=" + result.determinismMatch());
        for (String row : result.assertionResults()) {
            System.out.println("WS60 " + spec.shortId() + " " + row);
        }
        for (String row : result.hiddenResults()) {
            System.out.println("WS60 " + spec.shortId() + " " + row);
        }
        assertEquals("PASS", result.verdict(),
                () -> spec.id() + " not proven: " + result.rationale());
    }

    @Test
    void rqc3A03() throws Exception {
        runAndSeal(Ws60Scenarios.a03(), 4);
    }

    @Test
    void rqc3A04() throws Exception {
        runAndSeal(Ws60Scenarios.a04(), 4);
    }

    @Test
    void rqc3B01() throws Exception {
        // B01 is a bounded attempt with an expected UNKNOWN: Commander
        // singleton forbids P0's second Soul Warden natively (token route) and
        // every native Warden entry fires entry triggers, so the fixture's
        // nominal-40 lives are unreachable. The test passes when the run
        // correctly reports UNKNOWN with the structural blocker (fail-closed
        // unsupported handling); a miraculous PASS would fail here and be
        // promoted to credit by hand.
        Ws60Suite.Spec spec = Ws60Scenarios5.b01();
        Ws60Suite.SuiteResult result = Ws60Suite.execute(spec, 2);
        Ws60Suite.writeEvidence(result, EVIDENCE_DIR);
        System.out.println("WS60 " + spec.shortId() + " verdict=" + result.verdict()
                + " attempts=" + result.attempts().size()
                + " rationale=" + result.rationale());
        assertEquals("UNKNOWN", result.verdict(),
                () -> spec.id() + " unexpected verdict: " + result.verdict() + " "
                        + result.rationale());
    }

    @Test
    void rqc3C01() throws Exception {
        runAndSeal(Ws60Scenarios2.c01(), 6);
    }

    @Test
    void rqc3C03() throws Exception {
        runAndSeal(Ws60Scenarios2.c03(), 4);
    }

    @Test
    void rqc3D06() throws Exception {
        runAndSeal(Ws60Scenarios2.d06(), 6);
    }

    @Test
    void rqc3E01() throws Exception {
        runAndSeal(Ws60Scenarios3.e01(), 4);
    }

    @Test
    void rqc3E02() throws Exception {
        runAndSeal(Ws60Scenarios3.e02(), 6);
    }

    @Test
    void rqc3F01() throws Exception {
        runAndSeal(Ws60Scenarios3.f01(), 4);
    }

    @Test
    void rqc3G02() throws Exception {
        runAndSeal(Ws60Scenarios3.g02(), 4);
    }

    @Test
    void rqc3G03() throws Exception {
        runAndSeal(Ws60Scenarios4.g03(), 4);
    }

    @Test
    void rqc3G04() throws Exception {
        runAndSeal(Ws60Scenarios4.g04(), 4);
    }

    @Test
    void rqc3H01() throws Exception {
        runAndSeal(Ws60Scenarios4.h01(), 4);
    }

    @Test
    void rqc3I01() throws Exception {
        runAndSeal(Ws60Scenarios4.i01(), 4);
    }

    @Test
    void rqc3J02() throws Exception {
        runAndSeal(Ws60Scenarios5.j02(), 12);
    }
}

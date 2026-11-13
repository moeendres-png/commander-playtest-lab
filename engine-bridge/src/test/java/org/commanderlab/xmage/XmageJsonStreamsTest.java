package org.commanderlab.xmage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.io.StringWriter;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

/**
 * Bridge-lean #1264 step 1 (NEUTRAL): the streamed state hash and writer are
 * byte-identical to the former {@code deepCopy + remove + toString + SHA-256}.
 */
class XmageJsonStreamsTest {

    /** The implementation this change replaced, verbatim. */
    private static String referenceStateHash(JsonObject state) throws Exception {
        JsonObject normalized = state.deepCopy();
        normalized.remove("event_sequence");
        MessageDigest digest = MessageDigest.getInstance("SHA-256");
        return HexFormat.of().formatHex(
                digest.digest(normalized.toString().getBytes(StandardCharsets.UTF_8)));
    }

    private static List<JsonObject> samples() {
        List<JsonObject> samples = new ArrayList<>();
        samples.add(new JsonObject());

        JsonObject scalars = new JsonObject();
        scalars.addProperty("event_sequence", 42);
        scalars.addProperty("int", 7);
        scalars.addProperty("long", Long.MIN_VALUE);
        scalars.addProperty("double", 0.1d + 0.2d);
        scalars.addProperty("float", 1.5f);
        scalars.addProperty("neg_zero", -0.0d);
        scalars.addProperty("big", new BigInteger("123456789012345678901234567890"));
        scalars.addProperty("dec", new BigDecimal("1.2300E+5"));
        scalars.addProperty("nan", Double.NaN);
        scalars.addProperty("inf", Double.NEGATIVE_INFINITY);
        scalars.addProperty("bool_t", true);
        scalars.addProperty("bool_f", false);
        scalars.addProperty("char", 'x');
        scalars.add("null", JsonNull.INSTANCE);
        scalars.add("empty_array", new JsonArray());
        scalars.add("empty_object", new JsonObject());
        samples.add(scalars);

        JsonObject text = new JsonObject();
        text.addProperty("html", "<script>alert('x')&=\"q\"</script>    \u007f \u0000\u001f\t\r\n\\ /");
        text.addProperty("unicode", "Jötun Grunt éè 中文 😀 ́ ￿");
        text.addProperty("lone_high", "a\ud83d");
        text.addProperty("lone_low", "\ude00b");
        text.addProperty("high_then_escape", "\ud83d\n\ude00");
        text.addProperty("kéy \"quoted\"  ", "v");
        text.addProperty("event_sequence", "dropped at top level only");
        samples.add(text);

        // Long strings that cross the encoder's internal buffer at a surrogate pair boundary.
        for (int pad = 8180; pad < 8200; pad++) {
            JsonObject boundary = new JsonObject();
            boundary.addProperty("s", "x".repeat(pad) + "😀" + "y".repeat(10));
            samples.add(boundary);
        }

        JsonObject nested = new JsonObject();
        nested.addProperty("event_sequence", 1);
        JsonObject inner = new JsonObject();
        inner.addProperty("event_sequence", "kept: not top level");
        JsonArray matrix = new JsonArray();
        for (int i = 0; i < 5; i++) {
            JsonArray row = new JsonArray();
            for (int j = 0; j < 4; j++) {
                row.add(i * j);
                row.add(JsonNull.INSTANCE);
                row.add("c" + j);
                JsonArray deeper = new JsonArray();
                deeper.add(new JsonArray());
                deeper.add(inner.deepCopy());
                row.add(deeper);
            }
            matrix.add(row);
        }
        inner.add("matrix", matrix);
        nested.add("inner", inner);
        nested.add("list", matrix);
        samples.add(nested);

        // Parsed numbers are LazilyParsedNumber; the original text is kept in the output.
        samples.add(JsonParser.parseString(
                "{\"zeta\":1.0,\"alpha\":[1e2,-0,10000000000000000000000,0.10],\"event_sequence\":9,"
                        + "\"m\":{\"b\":null,\"a\":\"\\u00e9\\ud83d\\ude00\"}}").getAsJsonObject());
        return samples;
    }

    @Test
    void streamedHashEqualsDeepCopyToStringHash() throws Exception {
        for (JsonObject sample : samples()) {
            assertEquals(
                    referenceStateHash(sample),
                    XmageAuditEventLog.stateHash(sample),
                    () -> "hash differs for " + sample.toString().substring(0, Math.min(120, sample.toString().length())));
        }
    }

    @Test
    void hashDoesNotMutateTheState() throws Exception {
        for (JsonObject sample : samples()) {
            String before = sample.toString();
            XmageAuditEventLog.stateHash(sample);
            assertEquals(before, sample.toString());
        }
    }

    @Test
    void topLevelEventSequenceIsIgnoredAndNestedOneIsNot() {
        JsonObject a = new JsonObject();
        a.addProperty("x", 1);
        JsonObject b = a.deepCopy();
        b.addProperty("event_sequence", 99);
        assertEquals(XmageAuditEventLog.stateHash(a), XmageAuditEventLog.stateHash(b));

        JsonObject nestedA = new JsonObject();
        JsonObject innerA = new JsonObject();
        innerA.addProperty("event_sequence", 1);
        nestedA.add("inner", innerA);
        JsonObject nestedB = nestedA.deepCopy();
        nestedB.getAsJsonObject("inner").addProperty("event_sequence", 2);
        assertNotEquals(XmageAuditEventLog.stateHash(nestedA), XmageAuditEventLog.stateHash(nestedB));
    }

    @Test
    void writerOutputEqualsToString() throws IOException {
        for (JsonObject sample : samples()) {
            StringWriter out = new StringWriter();
            XmageJsonStreams.write(sample, out);
            assertEquals(sample.toString(), out.toString());
        }
        for (JsonElement scalar : new JsonElement[] {
                JsonNull.INSTANCE, new com.google.gson.JsonPrimitive("é<> "), new com.google.gson.JsonPrimitive(3)}) {
            StringWriter out = new StringWriter();
            XmageJsonStreams.write(scalar, out);
            assertEquals(scalar.toString(), out.toString());
        }
    }
}

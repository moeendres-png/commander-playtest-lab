package org.commanderlab.xmage;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.Strictness;
import com.google.gson.stream.JsonWriter;

import java.io.IOException;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;

/**
 * Streams JSON into a sink without building the intermediate string.
 *
 * <p>The bytes are exactly those of {@link JsonElement#toString()} (gson 2.15:
 * a fresh {@link JsonWriter} with {@link Strictness#LENIENT}, no indent, HTML
 * escaping off, nulls serialized), encoded as UTF-8 the way
 * {@code String.getBytes(UTF_8)} does it. {@link #WRITER_GSON} only carries
 * those settings into {@code Gson#toJson(JsonElement, JsonWriter)}; the
 * equality with {@code toString()} is pinned by {@code XmageJsonStreamsTest}.</p>
 */
final class XmageJsonStreams {

    /**
     * serializeNulls on, HTML escaping off (Gson defaults it ON, a bare JsonWriter has it off),
     * strictness left to the writer (LENIENT below).
     */
    private static final Gson WRITER_GSON = new GsonBuilder().serializeNulls().disableHtmlEscaping().create();

    private XmageJsonStreams() {
    }

    /** Writes the same characters as {@code element.toString()} to {@code sink}. */
    static void write(JsonElement element, Writer sink) throws IOException {
        JsonWriter writer = new JsonWriter(sink);
        writer.setStrictness(Strictness.LENIENT);
        WRITER_GSON.toJson(element, writer);
        writer.flush();
    }

    /**
     * SHA-256 (lowercase hex) of the UTF-8 bytes of
     * {@code state.toString()} for {@code state} without its top-level
     * {@code skippedKey} member. Neither copies the object nor materializes
     * the string. The object is only read, in iteration order.
     */
    static String sha256WithoutTopLevelKey(JsonObject state, String skippedKey) {
        MessageDigest digest = newSha256();
        try (Writer sink = new OutputStreamWriter(new DigestSink(digest), StandardCharsets.UTF_8)) {
            JsonWriter writer = new JsonWriter(sink);
            writer.setStrictness(Strictness.LENIENT);
            writer.beginObject();
            for (Map.Entry<String, JsonElement> entry : state.entrySet()) {
                if (entry.getKey().equals(skippedKey)) {
                    continue;
                }
                writer.name(entry.getKey());
                WRITER_GSON.toJson(entry.getValue(), writer);
            }
            writer.endObject();
            writer.flush();
        } catch (IOException exc) {
            throw new IllegalStateException("digest sink cannot fail", exc);
        }
        return HexFormat.of().formatHex(digest.digest());
    }

    private static MessageDigest newSha256() {
        try {
            return MessageDigest.getInstance("SHA-256");
        } catch (NoSuchAlgorithmException exc) {
            throw new IllegalStateException("SHA-256 is unavailable", exc);
        }
    }

    private static final class DigestSink extends OutputStream {
        private final MessageDigest digest;

        private DigestSink(MessageDigest digest) {
            this.digest = digest;
        }

        @Override
        public void write(int b) {
            digest.update((byte) b);
        }

        @Override
        public void write(byte[] b, int off, int len) {
            digest.update(b, off, len);
        }
    }
}

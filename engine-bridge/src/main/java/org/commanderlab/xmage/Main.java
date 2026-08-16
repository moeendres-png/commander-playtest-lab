package org.commanderlab.xmage;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

public final class Main {

    private Main() {
    }

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");

        /*
         * Fail before accepting requests if the real XMage dependency
         * cannot actually be loaded.
         */
        XmageProvider.verifyRuntimeLoaded();

        JsonlBridge bridge = new JsonlBridge();

        try (
                BufferedReader input = new BufferedReader(
                        new InputStreamReader(
                                System.in,
                                StandardCharsets.UTF_8
                        )
                );
                PrintWriter output = new PrintWriter(
                        System.out,
                        true,
                        StandardCharsets.UTF_8
                )
        ) {
            String line;

            while ((line = input.readLine()) != null) {
                if (line.isBlank()) {
                    continue;
                }

                JsonlBridge.Result result = bridge.handle(line);

                output.println(result.json());
                output.flush();

                if (result.shutdown()) {
                    break;
                }
            }
        }
    }
}
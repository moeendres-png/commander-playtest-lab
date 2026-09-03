package org.commanderlab.xmage;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.nio.charset.StandardCharsets;

/** Standalone launcher so WS-22 production bridge behavior is not changed. */
public final class XmageWs26QualificationMain {
    private XmageWs26QualificationMain() {}

    public static void main(String[] args) throws Exception {
        System.setProperty("java.awt.headless", "true");
        XmageProvider.verifyRuntimeLoaded();
        XmageWs26QualificationJsonlBridge bridge = new XmageWs26QualificationJsonlBridge();
        try (BufferedReader input = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));
             PrintWriter output = new PrintWriter(System.out, true, StandardCharsets.UTF_8)) {
            String line;
            while ((line = input.readLine()) != null) {
                if (line.isBlank()) continue;
                XmageWs26QualificationJsonlBridge.Result result = bridge.handle(line);
                output.println(result.json());
                output.flush();
                if (result.shutdown()) break;
            }
        }
    }
}

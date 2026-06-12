package org.aegisneuro.aegisneuro;

import android.content.Context;
import android.util.Log;

import com.google.android.gms.wearable.MessageClient;
import com.google.android.gms.wearable.MessageEvent;
import com.google.android.gms.wearable.Wearable;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

public final class AegisWatchRuntimeBridge {
    private static final String TAG = "AegisWatchRuntime";
    private static final String VITALS_PATH = "/aegis/watch/vitals";
    private static final String INBOX_FILE = "watch_payloads.jsonl";

    private static MessageClient.OnMessageReceivedListener listener;
    private static Context appContext;

    private AegisWatchRuntimeBridge() {
    }

    public static synchronized void start(Context context) {
        if (context == null) {
            return;
        }
        appContext = context.getApplicationContext();
        if (listener != null) {
            return;
        }

        listener = new MessageClient.OnMessageReceivedListener() {
            @Override
            public void onMessageReceived(MessageEvent messageEvent) {
                if (!VITALS_PATH.equals(messageEvent.getPath())) {
                    return;
                }
                writePayload(new String(messageEvent.getData(), StandardCharsets.UTF_8));
            }
        };
        Wearable.getMessageClient(appContext).addListener(listener);
        Log.i(TAG, "Runtime Watch listener started");
    }

    public static synchronized void stop() {
        if (listener != null && appContext != null) {
            Wearable.getMessageClient(appContext).removeListener(listener);
        }
        listener = null;
        Log.i(TAG, "Runtime Watch listener stopped");
    }

    private static void writePayload(String rawPayload) {
        String payload = rawPayload == null ? "" : rawPayload.trim();
        if (payload.isEmpty() || appContext == null) {
            return;
        }

        try {
            File root = appContext.getExternalFilesDir(null);
            if (root == null) {
                root = appContext.getFilesDir();
            }
            File inbox = new File(root, INBOX_FILE);
            try (FileOutputStream stream = new FileOutputStream(inbox, true)) {
                stream.write(payload.getBytes(StandardCharsets.UTF_8));
                stream.write('\n');
            }
            Log.i(TAG, "Watch payload written: " + payload);
        } catch (Exception exc) {
            Log.e(TAG, "Unable to write watch payload", exc);
        }
    }
}

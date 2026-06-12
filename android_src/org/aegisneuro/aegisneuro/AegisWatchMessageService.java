package org.aegisneuro.aegisneuro;

import android.util.Log;

import com.google.android.gms.wearable.MessageEvent;
import com.google.android.gms.wearable.WearableListenerService;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

public class AegisWatchMessageService extends WearableListenerService {
    private static final String TAG = "AegisWatchReceiver";
    private static final String VITALS_PATH = "/aegis/watch/vitals";
    private static final String INBOX_FILE = "watch_payloads.jsonl";

    @Override
    public void onMessageReceived(MessageEvent messageEvent) {
        if (!VITALS_PATH.equals(messageEvent.getPath())) {
            super.onMessageReceived(messageEvent);
            return;
        }

        String payload = new String(messageEvent.getData(), StandardCharsets.UTF_8).trim();
        if (payload.isEmpty()) {
            return;
        }

        try {
            File root = getExternalFilesDir(null);
            if (root == null) {
                root = getFilesDir();
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

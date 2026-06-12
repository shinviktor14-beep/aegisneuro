package org.aegisneuro.aegisneuro;

import android.content.Context;
import android.util.Log;

import com.google.android.gms.wearable.Node;
import com.google.android.gms.wearable.Wearable;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;

public final class AegisWatchConnectionBridge {
    private static final String TAG = "AegisWatchConnection";
    private static String cachedStatusJson = "{\"connected\":false,\"node_count\":0,\"nodes\":[],\"error\":null}";
    private static boolean refreshInFlight = false;

    private AegisWatchConnectionBridge() {
    }

    public static String getStatusJson(Context context) {
        refresh(context);
        synchronized (AegisWatchConnectionBridge.class) {
            return cachedStatusJson;
        }
    }

    private static synchronized void refresh(Context context) {
        if (context == null) {
            cachedStatusJson = "{\"connected\":false,\"node_count\":0,\"nodes\":[],\"error\":\"Activity unavailable\"}";
            return;
        }
        if (refreshInFlight) {
            return;
        }

        refreshInFlight = true;
        Wearable.getNodeClient(context.getApplicationContext()).getConnectedNodes()
            .addOnSuccessListener(AegisWatchConnectionBridge::cacheNodes)
            .addOnFailureListener(exc -> {
                Log.e(TAG, "Unable to read connected Wear nodes", exc);
                cacheError(exc.toString());
            })
            .addOnCompleteListener(task -> {
                synchronized (AegisWatchConnectionBridge.class) {
                    refreshInFlight = false;
                }
            });
    }

    private static synchronized void cacheNodes(List<Node> nodes) {
        JSONArray nodesJson = new JSONArray();
        try {
            for (Node node : nodes) {
                JSONObject nodeJson = new JSONObject();
                nodeJson.put("id", node.getId());
                nodeJson.put("display_name", node.getDisplayName());
                nodeJson.put("nearby", node.isNearby());
                nodesJson.put(nodeJson);
            }

            JSONObject status = new JSONObject();
            status.put("connected", !nodes.isEmpty());
            status.put("node_count", nodes.size());
            status.put("nodes", nodesJson);
            status.put("error", JSONObject.NULL);
            cachedStatusJson = status.toString();
        } catch (Exception exc) {
            cacheError(exc.toString());
        }
    }

    private static synchronized void cacheError(String error) {
        try {
            JSONObject status = new JSONObject();
            status.put("connected", false);
            status.put("node_count", 0);
            status.put("nodes", new JSONArray());
            status.put("error", error);
            cachedStatusJson = status.toString();
        } catch (Exception ignored) {
            cachedStatusJson = "{\"connected\":false,\"node_count\":0,\"nodes\":[],\"error\":\"json\"}";
        }
    }
}

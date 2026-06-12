package org.aegisneuro.aegisneuro;

import android.content.Context;
import android.util.Log;

import com.google.android.gms.wearable.CapabilityClient;
import com.google.android.gms.wearable.CapabilityInfo;
import com.google.android.gms.wearable.Node;
import com.google.android.gms.wearable.Wearable;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.List;
import java.util.Set;

public final class AegisWatchConnectionBridge {
    private static final String TAG = "AegisWatchConnection";
    private static final String VITALS_CAPABILITY = "aegisneuro_vitals";
    private static String cachedStatusJson = "{\"connected\":false,\"node_count\":0,\"nodes\":[],\"watch_app_ready\":false,\"capability_node_count\":0,\"capability_nodes\":[],\"error\":null}";
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
            cachedStatusJson = "{\"connected\":false,\"node_count\":0,\"nodes\":[],\"watch_app_ready\":false,\"capability_node_count\":0,\"capability_nodes\":[],\"error\":\"Activity unavailable\"}";
            return;
        }
        if (refreshInFlight) {
            return;
        }

        refreshInFlight = true;
        Context appContext = context.getApplicationContext();
        Wearable.getNodeClient(appContext).getConnectedNodes()
            .addOnSuccessListener(nodes ->
                Wearable.getCapabilityClient(appContext)
                    .getCapability(VITALS_CAPABILITY, CapabilityClient.FILTER_REACHABLE)
                    .addOnSuccessListener(capability -> cacheStatus(nodes, capability))
                    .addOnFailureListener(exc -> {
                        Log.e(TAG, "Unable to read Aegis watch capability", exc);
                        cacheStatus(nodes, null);
                    })
                    .addOnCompleteListener(task -> clearRefreshFlag())
            )
            .addOnFailureListener(exc -> {
                Log.e(TAG, "Unable to read connected Wear nodes", exc);
                cacheError(exc.toString());
                clearRefreshFlag();
            });
    }

    private static synchronized void clearRefreshFlag() {
        refreshInFlight = false;
    }

    private static synchronized void cacheStatus(List<Node> nodes, CapabilityInfo capability) {
        JSONArray nodesJson = new JSONArray();
        JSONArray capabilityNodesJson = new JSONArray();
        try {
            for (Node node : nodes) {
                JSONObject nodeJson = new JSONObject();
                nodeJson.put("id", node.getId());
                nodeJson.put("display_name", node.getDisplayName());
                nodeJson.put("nearby", node.isNearby());
                nodesJson.put(nodeJson);
            }

            Set<Node> capabilityNodes = capability == null
                ? java.util.Collections.<Node>emptySet()
                : capability.getNodes();
            for (Node node : capabilityNodes) {
                JSONObject nodeJson = new JSONObject();
                nodeJson.put("id", node.getId());
                nodeJson.put("display_name", node.getDisplayName());
                nodeJson.put("nearby", node.isNearby());
                capabilityNodesJson.put(nodeJson);
            }

            JSONObject status = new JSONObject();
            status.put("connected", !nodes.isEmpty());
            status.put("node_count", nodes.size());
            status.put("nodes", nodesJson);
            status.put("watch_app_ready", !capabilityNodes.isEmpty());
            status.put("capability_node_count", capabilityNodes.size());
            status.put("capability_nodes", capabilityNodesJson);
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
            status.put("watch_app_ready", false);
            status.put("capability_node_count", 0);
            status.put("capability_nodes", new JSONArray());
            status.put("error", error);
            cachedStatusJson = status.toString();
        } catch (Exception ignored) {
            cachedStatusJson = "{\"connected\":false,\"node_count\":0,\"nodes\":[],\"watch_app_ready\":false,\"capability_node_count\":0,\"capability_nodes\":[],\"error\":\"json\"}";
        }
    }
}

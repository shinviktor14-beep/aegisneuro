package org.aegisneuro.aegisneuro;

import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.os.ParcelUuid;
import android.util.Log;
import java.util.List;
import java.util.UUID;

/**
 * Concrete ScanCallback subclass — pyjnius cannot inherit abstract classes,
 * only interfaces. This wrapper forwards every callback to a single
 * onResult(String address, String name, String uuids, int rssi) method
 * that Python can override via @run_on_ui_thread.
 */
public final class AegisScanCallback extends ScanCallback {
    private static final String TAG = "AegisScan";
    private static final UUID HR_SERVICE = UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb");

    private long callbackPtr = 0;   // set from Python via pyjnius

    public void setCallbackPtr(long ptr) {
        this.callbackPtr = ptr;
    }

    // Called from Python to check if a ScanResult advertises HR service
    public static boolean hasHeartRateService(ScanResult result) {
        if (result.getScanRecord() == null) return false;
        List<ParcelUuid> uuids = result.getScanRecord().getServiceUuids();
        if (uuids == null) return false;
        for (ParcelUuid pu : uuids) {
            if (pu.getUuid().equals(HR_SERVICE)) return true;
        }
        // Also check service data keys
        if (result.getScanRecord().getServiceData() != null) {
            for (UUID u : result.getScanRecord().getServiceData().keySet()) {
                if (u.equals(HR_SERVICE)) return true;
            }
        }
        return false;
    }

    public static String getAddress(ScanResult result) {
        return result.getDevice().getAddress();
    }

    public static String getName(ScanResult result) {
        String name = result.getDevice().getName();
        return name != null ? name : "";
    }

    public static int getRssi(ScanResult result) {
        return result.getRssi();
    }

    @Override
    public void onScanResult(int callbackType, ScanResult result) {
        try {
            nativeOnResult(getAddress(result), getName(result), getRssi(result), hasHeartRateService(result) ? 1 : 0);
        } catch (Exception e) {
            Log.e(TAG, "onScanResult JNI error", e);
        }
    }

    @Override
    public void onBatchScanResults(List<ScanResult> results) {
        for (ScanResult r : results) {
            try {
                nativeOnResult(getAddress(r), getName(r), getRssi(r), hasHeartRateService(r) ? 1 : 0);
            } catch (Exception e) {
                Log.e(TAG, "onBatchScanResult JNI error", e);
            }
        }
    }

    @Override
    public void onScanFailed(int errorCode) {
        try {
            nativeOnError(errorCode);
        } catch (Exception e) {
            Log.e(TAG, "onScanFailed JNI error", e);
        }
    }

    // JNI callbacks — implemented in Python via pyjnius
    private native void nativeOnResult(String address, String name, int rssi, int hasHr);
    private native void nativeOnError(int errorCode);
}
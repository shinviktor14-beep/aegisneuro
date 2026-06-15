package org.aegisneuro.ble;

import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;

/**
 * Wrapper for ScanCallback that delegates to a simple Java interface.
 * This allows pyjnius PythonJavaClass (which uses java.lang.reflect.Proxy)
 * to implement the nested OnScanResultListener interface instead of the
 * abstract ScanCallback class.
 */
public class ScanCallbackWrapper extends ScanCallback {

    private final OnScanResultListener listener;

    public ScanCallbackWrapper(OnScanResultListener listener) {
        this.listener = listener;
    }

    @Override
    public void onScanResult(int callbackType, ScanResult result) {
        if (listener != null) {
            listener.onResult(result);
        }
    }

    @Override
    public void onScanFailed(int errorCode) {
        if (listener != null) {
            listener.onError(errorCode);
        }
    }

    /**
     * Simple interface that pyjnius can proxy via java.lang.reflect.Proxy.
     * PythonJavaClass should declare __javainterfaces__ = ["org/aegisneuro/ble/ScanCallbackWrapper$OnScanResultListener"]
     */
    public interface OnScanResultListener {
        void onResult(ScanResult result);
        void onError(int errorCode);
    }
}

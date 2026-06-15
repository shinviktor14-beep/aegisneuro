package org.aegisneuro.ble;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;

/**
 * Wrapper for BluetoothGattCallback that delegates to a simple Java interface.
 * This allows pyjnius PythonJavaClass (which uses java.lang.reflect.Proxy)
 * to implement the nested OnGattEventListener interface instead of the
 * abstract BluetoothGattCallback class.
 */
public class GattCallbackWrapper extends BluetoothGattCallback {

    private final OnGattEventListener listener;

    public GattCallbackWrapper(OnGattEventListener listener) {
        this.listener = listener;
    }

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        if (listener != null) {
            listener.onConnectionStateChange(status, newState);
        }
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        if (listener != null) {
            listener.onServicesDiscovered(status);
        }
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
        if (listener != null) {
            listener.onCharacteristicChanged(gatt, characteristic);
        }
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic, int status) {
        // API 33+ variant - delegate to the same listener, ignoring status
        if (listener != null) {
            listener.onCharacteristicChanged(gatt, characteristic);
        }
    }

    /**
     * Simple interface that pyjnius can proxy via java.lang.reflect.Proxy.
     * PythonJavaClass should declare __javainterfaces__ = ["org/aegisneuro/ble/GattCallbackWrapper$OnGattEventListener"]
     */
    public interface OnGattEventListener {
        void onConnectionStateChange(int status, int newState);
        void onServicesDiscovered(int status);
        void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic);
    }
}

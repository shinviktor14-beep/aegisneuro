package org.aegisneuro.aegisneuro;

import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothProfile;
import android.util.Log;

import java.util.UUID;

/**
 * Concrete BluetoothGattCallback subclass -- pyjnius cannot inherit
 * abstract classes, only interfaces. This wrapper forwards GATT events
 * to simple string/int methods that Python can override.
 *
 * Heart Rate Service: 0000180d-0000-1000-8000-00805f9b34fb
 * Heart Rate Measurement char: 00002a37-0000-1000-8000-00805f9b34fb
 * Client Characteristic Configuration: 00002902-0000-1000-8000-00805f9b34fb
 */
public final class AegisGattCallback extends BluetoothGattCallback {
    private static final String TAG = "AegisGatt";

    // Heart Rate Service & Characteristic UUIDs
    public static final UUID HR_SERVICE_UUID =
            UUID.fromString("0000180d-0000-1000-8000-00805f9b34fb");
    public static final UUID HR_MEASUREMENT_UUID =
            UUID.fromString("00002a37-0000-1000-8000-00805f9b34fb");
    public static final UUID CCCD_UUID =
            UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        String address = gatt.getDevice().getAddress();
        try {
            nativeOnConnectionState(address, status, newState);
        } catch (Exception e) {
            Log.e(TAG, "onConnectionStateChange JNI error", e);
        }
        if (newState == BluetoothProfile.STATE_DISCONNECTED) {
            gatt.close();
        }
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        String address = gatt.getDevice().getAddress();
        try {
            // Check if HR service exists
            BluetoothGattService hrService = gatt.getService(HR_SERVICE_UUID);
            int hasHr = (hrService != null) ? 1 : 0;
            nativeOnServicesDiscovered(address, status, hasHr);

            if (hrService != null) {
                BluetoothGattCharacteristic hrChar = hrService.getCharacteristic(HR_MEASUREMENT_UUID);
                if (hrChar != null) {
                    // Enable notifications
                    gatt.setCharacteristicNotification(hrChar, true);
                    BluetoothGattDescriptor descriptor = hrChar.getDescriptor(CCCD_UUID);
                    if (descriptor != null) {
                        descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                        gatt.writeDescriptor(descriptor);
                    }
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "onServicesDiscovered JNI error", e);
        }
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
        if (HR_MEASUREMENT_UUID.equals(characteristic.getUuid())) {
            byte[] value = characteristic.getValue();
            if (value != null && value.length > 0) {
                try {
                    // Parse Heart Rate value per Bluetooth SIG spec
                    int flags = value[0] & 0xFF;
                    int hrValue;
                    if ((flags & 0x01) != 0) {
                        // 16-bit HR format
                        hrValue = ((value[2] & 0xFF) << 8) | (value[1] & 0xFF);
                    } else {
                        // 8-bit HR format
                        hrValue = value[1] & 0xFF;
                    }

                    // Check for RR intervals
                    int rrCount = 0;
                    StringBuilder rrData = new StringBuilder();
                    if ((flags & 0x10) != 0 && value.length > 2) {
                        int offset = ((flags & 0x01) != 0) ? 3 : 2;
                        while (offset + 1 < value.length) {
                            int rr = ((value[offset + 1] & 0xFF) << 8) | (value[offset] & 0xFF);
                            rrData.append(rr).append(",");
                            rrCount++;
                            offset += 2;
                        }
                    }

                    nativeOnHeartRate(gatt.getDevice().getAddress(), hrValue, rrCount,
                            rrData.length() > 0 ? rrData.toString() : "");
                } catch (Exception e) {
                    Log.e(TAG, "onCharacteristicChanged parse error", e);
                }
            }
        }
    }

    @Override
    public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status) {
        String address = gatt.getDevice().getAddress();
        try {
            nativeOnDescriptorWrite(address, status);
        } catch (Exception e) {
            Log.e(TAG, "onDescriptorWrite JNI error", e);
        }
    }

    // JNI callbacks -- implemented in Python via pyjnius
    private native void nativeOnConnectionState(String address, int status, int newState);
    private native void nativeOnServicesDiscovered(String address, int status, int hasHr);
    private native void onHeartRate(String address, int bpm, int rrCount, String rrData);
    private native void nativeOnDescriptorWrite(String address, int status);

    // Rename to avoid clash -- called from onCharacteristicChanged
    private native void nativeOnHeartRate(String address, int bpm, int rrCount, String rrData);
}
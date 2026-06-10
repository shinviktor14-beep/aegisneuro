import asyncio
import struct
from bleak import BleakClient, BleakScanner

class PolarH10Client:
    def __init__(self, dsp_processor_callback):
        # Передаем коллбек — функцию из нашего DSP-модуля, 
        # куда мы будем отправлять каждый пойманный R-R интервал
        self.dsp_callback = dsp_processor_callback
        self.HR_CHARACTERISTIC = "00002a37-0000-1000-8000-00805f9b34fb"
        self.is_connected = False

    def hr_data_handler(self, sender, data):
        """
        Парсер BLE-пакетов от Polar H10.
        Разбирает байты по спецификации Bluetooth SIG.
        """
        first_byte = data[0]
        
        # Проверяем формат R-R интервалов (бит 4 в первом байте указывает на их наличие)
        rr_present = (first_byte & 0x10) != 0
        
        # Определяем, сколько байт занимает ЧСС (1 или 2 байта)
        hr_size = 2 if (first_byte & 0x01) else 1
        
        if rr_present:
            # R-R интервалы находятся в пакете после байта флагов и значения ЧСС
            offset = 1 + hr_size
            
            # Парсим все R-R интервалы, оставшиеся в пакете (каждый занимает 2 байта)
            while offset < len(data):
                # Polar передает R-R интервалы в формате 1/1024 секунды
                rr_raw = struct.unpack_from("<H", data, offset)[0]
                offset += 2
                
                # Переводим в чистые миллисекунды (ms) для нашего DSP
                rr_ms = int((rr_raw / 1024.0) * 1000.0)
                
                # Отправляем интервал напрямую в математический движок
                self.dsp_callback(rr_ms)

    async def connect_and_stream(self):
        """Сканирует эфир, находит Polar H10 и запускает поток данных"""
        print("[Bluetooth] Сканирование эфира в поисках Polar H10...")
        devices = await BleakScanner.discover()
        polar_device = None
        
        for d in devices:
            if d.name and "Polar H10" in d.name:
                polar_device = d
                break
                
        if not polar_device:
            print("[Bluetooth] Ошибка: Polar H10 не найден. Проверь, что он надет и смочен водой.")
            return

        print(f"[Bluetooth] Найден {polar_device.name} [{polar_device.address}]. Подключение...")
        
        async with BleakClient(polar_device.address) as client:
            self.is_connected = client.is_connected
            print(f"[Bluetooth] Успешно подключено к Polar H10: {self.is_connected}")
            
            # Включаем уведомления (Notifications) на нужную характеристику
            await client.start_notify(self.HR_CHARACTERISTIC, self.hr_data_handler)
            print("[Bluetooth] Стрим R-R интервалов запущен. Для выхода нажми Ctrl+C")
            
            # Удерживаем подключение активным
            while client.is_connected:
                await asyncio.sleep(1)

# Тест модуля работы с железом
if __name__ == "__main__":
    # Простейший тест-коллбек, который просто выводит пойманный интервал в консоль
    def dummy_dsp_callback(rr_ms):
        print(f"[Real Hardware] Пойман R-R интервал: {rr_ms} ms")

    polar_client = PolarH10Client(dsp_processor_callback=dummy_dsp_callback)
    
    try:
        asyncio.run(polar_client.connect_and_stream())
    except KeyboardInterrupt:
        print("\n[Bluetooth] Отключение по требованию пользователя.")
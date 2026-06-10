import cv2
import numpy as np
import matplotlib.pyplot as plt

# Включаем базовую веб-камеру
cap = cv2.VideoCapture(0)

print("=== AEGISNEURO CAMERA TEST ===")
print("Плотно, но БЕЗ СИЛЬНОГО НАЖАТИЯ прижми указательный палец к объективу веб-камеры.")
print("Обеспечь хороший доступ света (направь на палец настольную лампу или фонарик смартфона).")
print("Для выхода нажми клавишу 'Q'")

red_signals = []

while len(red_signals) < 300: # Собираем 300 кадров (около 10 секунд)
    ret, frame = cap.read()
    if not ret:
        break

    # Вырезаем центральный квадрат кадра, чтобы убрать шумы по краям
    h, w, _ = frame.shape
    roi = frame[h//3:2*h//3, w//3:2*w//3]

    # Считаем среднее значение КРАСНОГО канала (в OpenCV это индекс 2, так как формат BGR)
    avg_red = np.mean(roi[:, :, 2])
    red_signals.append(avg_red)

    # Показываем окно с тем, что видит камера (там должно быть все красным)
    cv2.imshow('Aegis Сamera Scanner', frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

# Выводим результат: график твоей пульсации
plt.figure(figsize=(12, 4))
plt.plot(red_signals, color='red', linewidth=2)
plt.title("Реальный кардио-сигнал с камеры (ФПГ)")
plt.xlabel("Кадры времени")
plt.ylabel("Интенсивность поглощения света")
plt.grid(True)
plt.show()
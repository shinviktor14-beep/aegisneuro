import logging

log = logging.getLogger(__name__)

class AegisMarketplace:
    def __init__(self):
        # Твои реферальные теги Amazon Associates (заменятся на реальные при регистрации)
        self.amazon_assoc_tag = "aegisneuro0c-20" 
        
        self.products = {
            "polar_h10": {
                "name": "Polar H10 Heart Rate Monitor",
                "description": "Золотой стандарт ЭКГ-мониторинга. Необходим для автоматического предиктивного сканирования во сне и во время тренировок.",
                "base_url": "https://www.amazon.com/dp/B07PM5VCHX"
            },
            "muse_2": {
                "name": "Muse 2: The Brain Sensing Headband",
                "description": "Нейро-обруч для считывания ЭЭГ. Позволяет ИИ калибровать Spatial 8D звук в реальном времени под текущие волны мозга.",
                "base_url": "https://www.amazon.com/dp/B07HL2562H"
            }
        }

    def generate_affiliate_link(self, product_key):
        """Генерирует готовую реферальную ссылку для Амазона"""
        if product_key in self.products:
            base = self.products[product_key]["base_url"]
            return f"{base}?tag={self.amazon_assoc_tag}"
        return None

    def get_upsell_trigger_message(self, user_scan_count, average_stress):
        """
        ИИ-логика: когда именно предложить пользователю купить датчики, 
        чтобы это не выглядело навязчивой рекламой.
        """
        if user_scan_count > 5 and average_stress > 500:
            return {
                "title": "🛡️ Повысить уровень защиты до 100%",
                "text": "ИИ AegisNeuro фиксирует у вас частые вегетативные перегрузки. Замер по камере эффективен, но для предиктивного перехвата штормов в режиме 24/7 (включая сон) мы рекомендуем подключить нагрудный ЭКГ-датчик Polar H10.",
                "action_link": self.generate_affiliate_link("polar_h10")
            }
        return None
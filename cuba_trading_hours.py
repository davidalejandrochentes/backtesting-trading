# Filtro de horarios optimizado para Cuba (UTC-4)
from datetime import datetime
import pytz

def is_good_trading_time_cuba(datetime_utc):
    """
    Filtro de horarios para trading desde Cuba (UTC-4)
    Retorna True si es buen momento para hacer trading
    """
    
    # Convertir a hora de Cuba (UTC-4)
    cuba_tz = pytz.timezone('America/Havana')  # UTC-4
    cuba_time = datetime_utc.astimezone(cuba_tz)
    
    hour = cuba_time.hour
    weekday = cuba_time.weekday()  # 0=Lunes, 6=Domingo
    
    # No operar en fines de semana
    if weekday >= 5:  # Sábado o Domingo
        return False
    
    # HORARIOS PREMIUM - Mayor prioridad
    premium_hours = [9, 10, 11, 12]  # 9:00 AM - 12:59 PM Cuba
    if hour in premium_hours:
        return True
    
    # HORARIOS BUENOS - Prioridad media
    good_hours = [4, 5, 6, 7, 13, 14, 15]  # Madrugada europea + tarde NY
    if hour in good_hours:
        return True
    
    # Resto de horarios: NO operar
    return False

def get_market_session_cuba(datetime_utc):
    """
    Identifica la sesión del mercado desde Cuba
    """
    cuba_tz = pytz.timezone('America/Havana')
    cuba_time = datetime_utc.astimezone(cuba_tz)
    hour = cuba_time.hour
    
    if 4 <= hour <= 8:
        return "LONDON_OPEN"
    elif 9 <= hour <= 12:
        return "LONDON_NY_OVERLAP"  # MEJOR SESIÓN
    elif 13 <= hour <= 15:
        return "NY_ACTIVE"
    elif 16 <= hour <= 17:
        return "NY_CLOSE"
    else:
        return "LOW_ACTIVITY"

# Integración con tu estrategia existente
class EnhancedBinaryOptionsStrategy(BinaryOptionsStrategy):
    """
    Estrategia mejorada con filtro de horarios para Cuba
    """
    
    def next(self):
        current_time = self.data.datetime.datetime(0)
        current_date = current_time.date()
        
        # NUEVO: Filtro de horarios para Cuba
        if not is_good_trading_time_cuba(current_time):
            if self.params.debug:
                session = get_market_session_cuba(current_time)
                print(f"⏰ Horario no óptimo: {current_time} - Sesión: {session}")
            return
        
        # Revisar trades que expiran
        self.check_expired_trades(current_time)
        
        # Control de frecuencia de trades
        if self.should_skip_trade(current_time, current_date):
            return
        
        # Identificar sesión actual para ajustar parámetros
        market_session = get_market_session_cuba(current_time)
        
        # Verificar señales con filtros mejorados por sesión
        if self.check_call_conditions_enhanced(market_session):
            self.enter_binary_trade('CALL', current_time)
        elif self.check_put_conditions_enhanced(market_session):
            self.enter_binary_trade('PUT', current_time)
    
    def check_call_conditions_enhanced(self, market_session):
        """
        Condiciones mejoradas que consideran la sesión del mercado
        """
        basic_conditions = self.check_call_conditions()  # Tu lógica original
        
        if not basic_conditions:
            return False
        
        # Filtros adicionales según la sesión
        if market_session == "LONDON_NY_OVERLAP":
            # En la mejor sesión, ser más exigente con ADX
            return self.adx[0] > 30 and basic_conditions
        
        elif market_session in ["LONDON_OPEN", "NY_ACTIVE"]:
            # En sesiones buenas, mantener filtros normales
            return basic_conditions
        
        else:
            # En otras sesiones, ser MUY selectivo
            return (self.adx[0] > 35 and 
                   self.rsi[0] > 50 and 
                   basic_conditions)
    
    def check_put_conditions_enhanced(self, market_session):
        """
        Condiciones mejoradas para PUT según la sesión
        """
        basic_conditions = self.check_put_conditions()  # Tu lógica original
        
        if not basic_conditions:
            return False
        
        # Filtros adicionales según la sesión
        if market_session == "LONDON_NY_OVERLAP":
            # En la mejor sesión, ser más exigente con ADX
            return self.adx[0] > 30 and basic_conditions
        
        elif market_session in ["LONDON_OPEN", "NY_ACTIVE"]:
            # En sesiones buenas, mantener filtros normales
            return basic_conditions
        
        else:
            # En otras sesiones, ser MUY selectivo
            return (self.adx[0] > 35 and 
                   self.rsi[0] < 50 and 
                   basic_conditions)

# Configuración optimizada para horarios cubanos
CUBA_OPTIMIZED_CONFIG = {
    'ema1_period': 8,
    'ema2_period': 16,
    'ema3_period': 24,
    'st_period': 10,
    'st_multiplier': 3.0,
    'adx_threshold': 25,  # Base, se ajusta por sesión
    'supertrend_delay_bars': 4,  # Más agresivo en horarios premium
    'expiry_minutes': 3,  # Corto para aprovechar volatilidad
    'max_trades_per_day': 8,  # Aumentado para horarios limitados
    'min_time_between_trades': 5,  # Reducido en horarios premium
    'debug': True
}

# Función para mostrar horarios en Cuba
def show_cuba_trading_schedule():
    """
    Muestra los horarios óptimos en hora de Cuba
    """
    print("🇨🇺 HORARIOS ÓPTIMOS PARA TRADING EN CUBA (UTC-4)")
    print("=" * 55)
    print("🥇 PREMIUM (9:00 AM - 12:59 PM): Overlap Londres-NY")
    print("🥈 BUENOS (4:00 AM - 8:59 AM): Apertura Londres") 
    print("🥉 BUENOS (1:00 PM - 3:59 PM): Nueva York activo")
    print("❌ EVITAR (4:00 PM - 3:59 AM): Baja actividad")
    print("=" * 55)
    print("💡 Consejo: Concéntrate en las horas PREMIUM para mejores resultados")

if __name__ == "__main__":
    show_cuba_trading_schedule()
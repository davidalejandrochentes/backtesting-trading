# data_downloader.py
import yfinance as yf
import pandas as pd
import numpy as np  # ← AGREGADO: Import faltante
from datetime import datetime, timedelta

def download_eurusd_data(days=30):
    """
    Descarga datos de EUR/USD de los últimos N días
    """
    print("📥 Descargando datos de EUR/USD...")
    
    # Calcular fechas
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    try:
        # Descargar datos usando yfinance
        # EURUSD=X es el símbolo para EUR/USD en Yahoo Finance
        ticker = "EURUSD=X"
        
        # Configurar yfinance para evitar warnings
        data = yf.download(
            ticker, 
            start=start_date, 
            end=end_date, 
            interval="5m",
            auto_adjust=True,  # Para evitar el FutureWarning
            progress=False     # Para menos ruido en la salida
        )
        
        if data.empty:
            print("❌ No se pudieron descargar datos")
            return None
        
        # Limpiar y preparar datos
        data.reset_index(inplace=True)
        
        # Ajustar nombres de columnas dependiendo de la estructura
        if 'Datetime' in data.columns:
            data.rename(columns={'Datetime': 'datetime'}, inplace=True)
        elif 'Date' in data.columns:
            data.rename(columns={'Date': 'datetime'}, inplace=True)
        
        # Normalizar nombres de columnas
        data.columns = [col.lower() for col in data.columns]
        
        # Asegurar que tenemos las columnas correctas
        required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            print("❌ Estructura de datos inesperada")
            print(f"Columnas disponibles: {list(data.columns)}")
            return None
        
        # Seleccionar solo las columnas que necesitamos
        data = data[required_cols]
        
        # Remover filas con valores NaN
        data = data.dropna()
        
        if len(data) == 0:
            print("❌ No hay datos válidos después de la limpieza")
            return None
        
        # Guardar en CSV
        filename = f"eurusd_5min_{days}days.csv"
        data.to_csv(filename, index=False)
        
        print(f"✅ Datos guardados en: {filename}")
        print(f"📊 Total de velas: {len(data)}")
        print(f"📅 Periodo: {data['datetime'].min()} a {data['datetime'].max()}")
        
        return filename
        
    except Exception as e:
        print(f"❌ Error descargando datos: {str(e)}")
        return None

def create_sample_data(days=90):
    """
    Crear datos sintéticos para pruebas si no se pueden descargar datos reales
    """
    print(f"🔄 Creando datos sintéticos para {days} días de pruebas...")
    
    # Calcular número de velas (5 minutos = 12 velas por hora, 24h por día)
    velas_por_dia = 12 * 24  # 288 velas por día
    total_velas = days * velas_por_dia
    
    print(f"📊 Generando {total_velas:,} velas de 5 minutos...")
    
    # Generar fechas cada 5 minutos
    start_date = datetime.now() - timedelta(days=days)
    dates = pd.date_range(start=start_date, periods=total_velas, freq='5min')
    
    # Generar precios sintéticos que simulen EUR/USD
    np.random.seed(42)  # Para resultados reproducibles
    
    # Precio base EUR/USD
    base_price = 1.0800
    
    # Generar serie de precios con más variabilidad y patrones realistas
    returns = np.random.normal(0, 0.0008, len(dates))  # Volatilidad ligeramente mayor
    trend_changes = np.random.choice([0, 1], len(dates), p=[0.98, 0.02])  # 2% probabilidad de cambio de tendencia
    
    prices = [base_price]
    current_trend = 1  # 1 = alcista, -1 = bajista
    trend_strength = 0.0001
    
    for i in range(1, len(dates)):
        # Cambios de tendencia aleatorios
        if trend_changes[i]:
            current_trend *= -1
            trend_strength = np.random.uniform(0.00005, 0.0003)
        
        # Tendencia actual
        trend = current_trend * trend_strength
        
        # Mean reversion (vuelta a la media)
        mean_reversion = (base_price - prices[-1]) * 0.0008
        
        # Volatilidad de fin de semana (menor)
        weekend_factor = 0.3 if dates[i].weekday() >= 5 else 1.0
        
        # Sesiones de trading (mayor volatilidad en horas activas)
        hour = dates[i].hour
        session_factor = 1.5 if 7 <= hour <= 17 else 0.7  # Sesión europea/americana más activa
        
        # Precio nuevo
        total_change = (returns[i] * weekend_factor * session_factor) + trend + mean_reversion
        new_price = prices[-1] * (1 + total_change)
        
        # Mantener precio en rango realista EUR/USD
        new_price = max(0.9500, min(1.2500, new_price))
        prices.append(new_price)
    
    # Crear OHLC basado en los precios con mayor realismo
    data = []
    for i in range(len(dates)):
        price = prices[i]
        
        # Volatilidad intrabarra más realista
        hour = dates[i].hour
        volatility_factor = 1.5 if 8 <= hour <= 16 else 0.8  # Mayor volatilidad en horas activas
        base_spread = np.random.uniform(0.0002, 0.0012) * volatility_factor
        
        # Crear vela realista
        direction = np.random.choice([-1, 1], p=[0.48, 0.52])  # Ligero sesgo alcista
        body_size = np.random.uniform(0.0001, base_spread * 0.8)
        wick_size = np.random.uniform(0.0001, base_spread * 1.2)
        
        if direction > 0:  # Vela verde
            open_price = price - body_size/2
            close = price + body_size/2
            high = close + wick_size
            low = open_price - wick_size/2
        else:  # Vela roja
            open_price = price + body_size/2
            close = price - body_size/2
            high = open_price + wick_size
            low = close - wick_size/2
        
        # Asegurar que OHLC sea lógicamente consistente
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        # Volumen más realista basado en la volatilidad y hora
        base_volume = 2000
        volume_factor = volatility_factor * (1 + abs(close - open_price) * 10000)
        volume = int(base_volume * volume_factor * np.random.uniform(0.5, 2.0))
        
        data.append({
            'datetime': dates[i],
            'open': round(open_price, 5),
            'high': round(high, 5),
            'low': round(low, 5),
            'close': round(close, 5),
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    filename = f"eurusd_5min_synthetic_{days}days.csv"
    df.to_csv(filename, index=False)
    
    print(f"✅ Datos sintéticos guardados en: {filename}")
    print(f"📊 Total de velas: {len(df)}")
    print(f"📅 Periodo: {df['datetime'].min()} a {df['datetime'].max()}")
    
    return filename

def try_alternative_sources():
    """
    Intentar fuentes alternativas de datos
    """
    print("🔄 Intentando fuentes alternativas...")
    
    # Lista de tickers alternativos para EUR/USD
    alternative_tickers = [
        "EUR=X",  # Alternativa 1
        "EURUSD=X",  # Original
    ]
    
    for ticker in alternative_tickers:
        print(f"📡 Probando ticker: {ticker}")
        try:
            # Período más corto para prueba rápida
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)
            
            data = yf.download(
                ticker, 
                start=start_date, 
                end=end_date, 
                interval="5m",
                auto_adjust=True,
                progress=False
            )
            
            if not data.empty and len(data) > 100:
                print(f"✅ Datos encontrados con {ticker}")
                
                # Procesar datos
                data.reset_index(inplace=True)
                if 'Datetime' in data.columns:
                    data.rename(columns={'Datetime': 'datetime'}, inplace=True)
                elif 'Date' in data.columns:
                    data.rename(columns={'Date': 'datetime'}, inplace=True)
                
                data.columns = [col.lower() for col in data.columns]
                data = data.dropna()
                
                if len(data) > 0:
                    filename = "eurusd_5min_alternative.csv"
                    data.to_csv(filename, index=False)
                    print(f"✅ Datos guardados en: {filename}")
                    return filename
                    
        except Exception as e:
            print(f"❌ Error con {ticker}: {str(e)}")
            continue
    
    return None

if __name__ == "__main__":
    print("=== DESCARGADOR DE DATOS EUR/USD ===")
    
    # Opción 1: Intentar descargar datos reales
    print("1. Intentando descargar datos reales...")
    filename = download_eurusd_data(days=30)
    
    # Opción 2: Intentar fuentes alternativas
    if filename is None:
        print("\n2. Intentando fuentes alternativas...")
        filename = try_alternative_sources()
    
    # Opción 3: Crear datos sintéticos
    if filename is None:
        print("\n3. Creando datos sintéticos para pruebas...")
        
        # Preguntar cuántos días de datos quiere el usuario
        try:
            days_input = input("¿Cuántos días de datos sintéticos quieres generar? (por defecto 90): ").strip()
            days = int(days_input) if days_input else 90
            
            # Validar rango razonable
            if days < 7:
                print("⚠️ Mínimo 7 días, usando 7...")
                days = 7
            elif days > 365:
                print("⚠️ Máximo 365 días, usando 365...")
                days = 365
                
        except ValueError:
            print("⚠️ Valor inválido, usando 90 días por defecto...")
            days = 90
            
        filename = create_sample_data(days=days)
    
    if filename:
        print(f"\n🎯 Archivo listo para usar: {filename}")
        print("\n▶️ Siguiente paso: ejecutar 'python main_backtest.py'")
        
        # Mostrar preview de los datos
        try:
            df = pd.read_csv(filename)
            print(f"\n📋 Preview de los datos ({filename}):")
            print(df.head())
            print(f"\n📈 Rango de precios: {df['low'].min():.5f} - {df['high'].max():.5f}")
        except:
            pass
    else:
        print("\n❌ No se pudieron obtener datos de ninguna fuente")
        print("💡 Verifica tu conexión a internet e inténtalo de nuevo")
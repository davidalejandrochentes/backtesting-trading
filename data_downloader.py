# data_downloader.py - Versión mejorada con soporte para 5 años de datos
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os

def download_eurusd_data_extended(days=1825):  # 5 años por defecto
    """
    Descarga datos de EUR/USD hasta 5 años históricos (máximo disponible en Yahoo Finance)
    Usa múltiples descargas para evitar límites de la API
    """
    print(f"📥 Descargando datos de EUR/USD para {days} días ({days/365:.1f} años)...")
    
    # Validar rango (Yahoo Finance tiene límites)
    if days > 1825:  # ~5 años
        print("⚠️ Máximo 5 años disponibles, ajustando...")
        days = 1825
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Para períodos largos, dividir en chunks para evitar límites de API
    chunk_days = 60  # Descargar en chunks de 2 meses
    all_data = []
    
    current_end = end_date
    
    try:
        while current_end > start_date:
            current_start = max(start_date, current_end - timedelta(days=chunk_days))
            
            print(f"📊 Descargando chunk: {current_start.strftime('%Y-%m-%d')} a {current_end.strftime('%Y-%m-%d')}")
            
            # Probar diferentes tickers
            for ticker in ["EURUSD=X", "EUR=X"]:
                try:
                    chunk_data = yf.download(
                        ticker,
                        start=current_start,
                        end=current_end,
                        interval="5m",
                        auto_adjust=True,
                        progress=False
                    )
                    
                    if not chunk_data.empty:
                        chunk_data.reset_index(inplace=True)
                        all_data.append(chunk_data)
                        print(f"✅ Chunk descargado: {len(chunk_data)} velas con {ticker}")
                        break
                        
                except Exception as e:
                    print(f"❌ Error con {ticker}: {str(e)}")
                    continue
            
            # Mover al siguiente chunk
            current_end = current_start
            
            # Pausa para evitar rate limiting
            time.sleep(0.5)
        
        if not all_data:
            print("❌ No se pudieron descargar datos")
            return None
        
        # Combinar todos los chunks
        print("🔄 Combinando datos...")
        data = pd.concat(all_data, ignore_index=True)
        
        # Limpiar y preparar datos
        if 'Datetime' in data.columns:
            data.rename(columns={'Datetime': 'datetime'}, inplace=True)
        elif 'Date' in data.columns:
            data.rename(columns={'Date': 'datetime'}, inplace=True)
        
        data.columns = [col.lower() for col in data.columns]
        
        # Verificar columnas requeridas
        required_cols = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_cols):
            print(f"❌ Columnas faltantes. Disponibles: {list(data.columns)}")
            return None
        
        data = data[required_cols]
        data = data.dropna()
        data = data.drop_duplicates(subset=['datetime'])
        data = data.sort_values('datetime')
        data.reset_index(drop=True, inplace=True)
        
        if len(data) == 0:
            print("❌ No hay datos válidos después de la limpieza")
            return None
        
        # Guardar archivo
        filename = f"eurusd_5min_{days}days_historical.csv"
        data.to_csv(filename, index=False)
        
        print(f"✅ Datos históricos guardados en: {filename}")
        print(f"📊 Total de velas: {len(data):,}")
        print(f"📅 Período: {data['datetime'].min()} a {data['datetime'].max()}")
        print(f"💰 Rango de precios: {data['low'].min():.5f} - {data['high'].max():.5f}")
        
        return filename
        
    except Exception as e:
        print(f"❌ Error descargando datos: {str(e)}")
        return None

def create_synthetic_data_5years(days=1825):
    """
    Crear datos sintéticos más realistas para hasta 5 años
    Incluye patrones estacionales y tendencias macro
    """
    print(f"🔄 Creando datos sintéticos de alta calidad para {days} días ({days/365:.1f} años)...")
    
    # Calcular número de velas
    velas_por_dia = 12 * 24  # 288 velas de 5min por día
    total_velas = days * velas_por_dia
    
    print(f"📊 Generando {total_velas:,} velas de 5 minutos...")
    
    # Fechas
    start_date = datetime.now() - timedelta(days=days)
    dates = pd.date_range(start=start_date, periods=total_velas, freq='5min')
    
    # Semilla para reproducibilidad
    np.random.seed(42)
    
    # Parámetros más realistas para EUR/USD
    base_price = 1.0800
    annual_drift = 0.02  # 2% drift anual promedio
    daily_vol = 0.008   # Volatilidad diaria típica
    
    # Generar componentes de precio más sofisticados
    # 1. Tendencia macro (ciclos económicos)
    macro_cycle_days = 365 * 2  # Ciclo de 2 años
    macro_trend = np.sin(2 * np.pi * np.arange(len(dates)) / (macro_cycle_days * velas_por_dia)) * 0.15
    
    # 2. Estacionalidad (patrones intra-año)
    day_of_year = np.array([d.timetuple().tm_yday for d in dates])
    seasonal = np.sin(2 * np.pi * day_of_year / 365) * 0.05
    
    # 3. Patrones semanales (menos actividad fines de semana)
    weekday = np.array([d.weekday() for d in dates])
    weekly_pattern = np.where(weekday >= 5, 0.7, 1.0)  # Reducir actividad fines de semana
    
    # 4. Patrones diarios (sesiones de trading)
    hour = np.array([d.hour for d in dates])
    daily_pattern = np.where(
        ((hour >= 8) & (hour <= 16)) |  # Sesión europea
        ((hour >= 13) & (hour <= 21)),  # Sesión americana
        1.2, 0.8
    )
    
    # 5. Generar retornos con estructura más compleja
    base_returns = np.random.normal(0, daily_vol / np.sqrt(velas_por_dia), len(dates))
    
    # Aplicar heterocedasticidad (volatilidad variable)
    garch_factor = np.ones(len(dates))
    for i in range(1, len(dates)):
        # Modelo GARCH simplificado
        garch_factor[i] = 0.95 * garch_factor[i-1] + 0.05 * (base_returns[i-1]**2) + 0.02
    
    # Aplicar todos los factores
    returns = base_returns * garch_factor * weekly_pattern * daily_pattern
    
    # 6. Generar niveles de precio
    log_prices = [np.log(base_price)]
    
    for i in range(1, len(dates)):
        # Drift ajustado por tendencia macro y estacional
        drift = annual_drift / (365 * velas_por_dia) + macro_trend[i] * 0.01 + seasonal[i] * 0.005
        
        # Mean reversion hacia precio base
        mean_reversion = -0.01 * (log_prices[-1] - np.log(base_price)) / (365 * velas_por_dia)
        
        # Nuevo log-precio
        new_log_price = log_prices[-1] + drift + mean_reversion + returns[i]
        
        # Mantener en rango realista
        new_price = np.exp(new_log_price)
        if new_price < 0.8000:
            new_log_price = np.log(0.8000)
        elif new_price > 1.4000:
            new_log_price = np.log(1.4000)
            
        log_prices.append(new_log_price)
    
    prices = np.exp(log_prices)
    
    # 7. Crear datos OHLCV realistas
    print("🎯 Generando datos OHLCV...")
    data = []
    
    for i in range(len(dates)):
        price = prices[i]
        
        # Volatilidad intrabarra basada en patrones
        intrabar_vol = daily_vol / np.sqrt(velas_por_dia) * daily_pattern[i] * weekly_pattern[i]
        
        # Spread bid-ask simulado
        spread = np.random.uniform(0.00008, 0.00015)  # 0.8-1.5 pips típico
        
        # Dirección de la vela basada en momentum
        momentum = returns[max(0, i-5):i+1].sum() if i >= 5 else returns[i]
        bullish_prob = 0.5 + np.tanh(momentum * 100) * 0.2  # Entre 0.3 y 0.7
        is_bullish = np.random.random() < bullish_prob
        
        # Tamaño del cuerpo de la vela
        body_size = abs(np.random.normal(0, intrabar_vol * 0.6))
        wick_size_upper = abs(np.random.normal(0, intrabar_vol * 0.8))
        wick_size_lower = abs(np.random.normal(0, intrabar_vol * 0.8))
        
        if is_bullish:
            open_price = price - body_size / 2
            close = price + body_size / 2
            high = close + wick_size_upper
            low = open_price - wick_size_lower
        else:
            open_price = price + body_size / 2
            close = price - body_size / 2
            high = open_price + wick_size_upper
            low = close - wick_size_lower
        
        # Asegurar consistencia OHLC
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
        # Volumen realista
        base_volume = 2500
        volume_multiplier = daily_pattern[i] * weekly_pattern[i] * (1 + abs(body_size) * 50000)
        volume = int(base_volume * volume_multiplier * np.random.uniform(0.3, 2.5))
        
        data.append({
            'datetime': dates[i],
            'open': round(open_price, 5),
            'high': round(high, 5),
            'low': round(low, 5),
            'close': round(close, 5),
            'volume': volume
        })
        
        # Progreso cada 10%
        if (i + 1) % (len(dates) // 10) == 0:
            progress = (i + 1) / len(dates) * 100
            print(f"⏳ Progreso: {progress:.0f}%")
    
    # Crear DataFrame y guardar
    df = pd.DataFrame(data)
    filename = f"eurusd_5min_synthetic_{days}days.csv"
    df.to_csv(filename, index=False)
    
    print(f"✅ Datos sintéticos guardados en: {filename}")
    print(f"📊 Total de velas: {len(df):,}")
    print(f"📅 Período: {df['datetime'].min()} a {df['datetime'].max()}")
    print(f"💰 Rango de precios: {df['low'].min():.5f} - {df['high'].max():.5f}")
    
    return filename

def download_eurusd_data(days=30):
    """
    Versión original mantenida para compatibilidad
    """
    return download_eurusd_data_extended(days)

def create_sample_data(days=90):
    """
    Versión original mantenida para compatibilidad
    """
    if days > 365:
        return create_synthetic_data_5years(days)
    
    # Código original para períodos cortos...
    print(f"🔄 Creando datos sintéticos para {days} días de pruebas...")
    
    velas_por_dia = 12 * 24
    total_velas = days * velas_por_dia
    
    print(f"📊 Generando {total_velas:,} velas de 5 minutos...")
    
    start_date = datetime.now() - timedelta(days=days)
    dates = pd.date_range(start=start_date, periods=total_velas, freq='5min')
    
    np.random.seed(42)
    base_price = 1.0800
    
    returns = np.random.normal(0, 0.0008, len(dates))
    trend_changes = np.random.choice([0, 1], len(dates), p=[0.98, 0.02])
    
    prices = [base_price]
    current_trend = 1
    trend_strength = 0.0001
    
    for i in range(1, len(dates)):
        if trend_changes[i]:
            current_trend *= -1
            trend_strength = np.random.uniform(0.00005, 0.0003)
        
        trend = current_trend * trend_strength
        mean_reversion = (base_price - prices[-1]) * 0.0008
        weekend_factor = 0.3 if dates[i].weekday() >= 5 else 1.0
        hour = dates[i].hour
        session_factor = 1.5 if 7 <= hour <= 17 else 0.7
        
        total_change = (returns[i] * weekend_factor * session_factor) + trend + mean_reversion
        new_price = prices[-1] * (1 + total_change)
        new_price = max(0.9500, min(1.2500, new_price))
        prices.append(new_price)
    
    data = []
    for i in range(len(dates)):
        price = prices[i]
        hour = dates[i].hour
        volatility_factor = 1.5 if 8 <= hour <= 16 else 0.8
        base_spread = np.random.uniform(0.0002, 0.0012) * volatility_factor
        
        direction = np.random.choice([-1, 1], p=[0.48, 0.52])
        body_size = np.random.uniform(0.0001, base_spread * 0.8)
        wick_size = np.random.uniform(0.0001, base_spread * 1.2)
        
        if direction > 0:
            open_price = price - body_size/2
            close = price + body_size/2
            high = close + wick_size
            low = open_price - wick_size/2
        else:
            open_price = price + body_size/2
            close = price - body_size/2
            high = open_price + wick_size
            low = close - wick_size/2
        
        high = max(high, open_price, close)
        low = min(low, open_price, close)
        
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
    print(f"📅 Período: {df['datetime'].min()} a {df['datetime'].max()}")
    
    return filename

def try_alternative_sources():
    """
    Intentar fuentes alternativas de datos
    """
    print("🔄 Intentando fuentes alternativas...")
    
    alternative_tickers = [
        "EUR=X",
        "EURUSD=X",
    ]
    
    for ticker in alternative_tickers:
        print(f"🔡 Probando ticker: {ticker}")
        try:
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
    print("=== DESCARGADOR DE DATOS EUR/USD - VERSIÓN EXTENDIDA ===")
    print("🎯 Soporte para hasta 5 años de datos históricos")
    
    # Menú de opciones
    print("\nOpciones disponibles:")
    print("1. Descargar datos reales (hasta 5 años)")
    print("2. Generar datos sintéticos de alta calidad")
    print("3. Modo automático (intenta real, luego sintético)")
    
    try:
        option = input("\nSelecciona una opción (1-3) [3]: ").strip() or "3"
        
        # Preguntar duración
        days_input = input("¿Cuántos días de datos necesitas? (30-1825 días, max ~5 años) [365]: ").strip()
        days = int(days_input) if days_input else 365
        
        # Validar rango
        if days < 7:
            print("⚠️ Mínimo 7 días, ajustando...")
            days = 7
        elif days > 1825:
            print("⚠️ Máximo 5 años (1825 días), ajustando...")
            days = 1825
        
        filename = None
        
        if option == "1":
            # Solo datos reales
            print(f"\n1. Descargando datos reales para {days} días...")
            filename = download_eurusd_data_extended(days)
            
        elif option == "2":
            # Solo datos sintéticos
            print(f"\n2. Generando datos sintéticos para {days} días...")
            if days > 365:
                filename = create_synthetic_data_5years(days)
            else:
                filename = create_sample_data(days)
                
        else:  # option == "3" o default
            # Modo automático
            print(f"\n1. Intentando descargar datos reales para {days} días...")
            filename = download_eurusd_data_extended(days)
            
            if filename is None:
                print("\n2. Intentando fuentes alternativas...")
                filename = try_alternative_sources()
            
            if filename is None:
                print(f"\n3. Generando datos sintéticos para {days} días...")
                if days > 365:
                    filename = create_synthetic_data_5years(days)
                else:
                    filename = create_sample_data(days)
        
        if filename:
            print(f"\n🎯 ¡ÉXITO! Archivo listo: {filename}")
            print(f"📈 Datos disponibles: {days} días ({days/365:.1f} años)")
            
            # Mostrar estadísticas
            try:
                df = pd.read_csv(filename)
                print(f"\n📋 Estadísticas del archivo:")
                print(f"   📊 Velas totales: {len(df):,}")
                print(f"   📅 Desde: {df['datetime'].min()}")
                print(f"   📅 Hasta: {df['datetime'].max()}")
                print(f"   💰 Precio mínimo: {df['low'].min():.5f}")
                print(f"   💰 Precio máximo: {df['high'].max():.5f}")
                print(f"   📈 Precio promedio: {df['close'].mean():.5f}")
                print(f"   📦 Tamaño archivo: {os.path.getsize(filename)/1024/1024:.1f} MB")
                
                print(f"\n📋 Vista previa de los datos:")
                print(df.head(3).to_string(index=False))
                
            except Exception as e:
                print(f"⚠️ Error mostrando estadísticas: {e}")
            
            print(f"\n▶️ Siguiente paso: ejecutar 'python main_backtest.py' con {filename}")
            
        else:
            print("\n❌ No se pudieron obtener datos de ninguna fuente")
            print("💡 Verifica tu conexión a internet e inténtalo de nuevo")
            
    except ValueError:
        print("❌ Valor inválido ingresado")
    except KeyboardInterrupt:
        print("\n⏹️ Operación cancelada por el usuario")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
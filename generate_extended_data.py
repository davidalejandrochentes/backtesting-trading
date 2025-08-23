#!/usr/bin/env python3
# generate_extended_data.py
"""
Generador de datos sintéticos extendidos para backtesting de estrategias forex
Permite crear datasets de diferentes tamaños para pruebas más robustas
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def generate_realistic_forex_data(days=90, symbol="EURUSD", base_price=1.0800):
    """
    Genera datos forex sintéticos pero realistas
    
    Args:
        days (int): Número de días de datos a generar
        symbol (str): Símbolo del par de divisas
        base_price (float): Precio base inicial
    
    Returns:
        str: Nombre del archivo CSV generado
    """
    
    print(f"🔄 Generando {days} días de datos para {symbol}...")
    
    # Calcular parámetros
    velas_por_dia = 288  # 12 velas/hora * 24 horas = 288 velas/día (5min)
    total_velas = days * velas_por_dia
    
    print(f"📊 Total de velas a generar: {total_velas:,}")
    
    # Generar fechas
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, periods=total_velas, freq='5min')
    
    # Configurar generador de números aleatorios
    np.random.seed(42)  # Para reproducibilidad
    
    # Parámetros de mercado
    daily_volatility = 0.012  # 1.2% volatilidad diaria típica
    intraday_vol = daily_volatility / np.sqrt(288)  # Volatilidad por vela de 5min
    
    # Generar precios con patrones realistas
    prices = []
    returns = []
    trends = []
    
    # Estado inicial
    current_price = base_price
    current_trend = 0  # -1 bajista, 0 neutral, 1 alcista
    trend_persistence = 0  # Cuántas velas lleva la tendencia actual
    
    for i, date in enumerate(dates):
        # Factores temporales
        hour = date.hour
        day_of_week = date.weekday()  # 0=lunes, 6=domingo
        
        # Actividad por sesión
        if 7 <= hour <= 9:  # Apertura europea
            session_factor = 1.8
        elif 13 <= hour <= 15:  # Solapamiento Europa-América
            session_factor = 2.2
        elif 21 <= hour <= 23:  # Apertura asiática
            session_factor = 1.3
        elif day_of_week >= 5:  # Fin de semana
            session_factor = 0.3
        else:
            session_factor = 1.0
        
        # Cambios de tendencia estocásticos
        if trend_persistence > 50 or np.random.random() < 0.02:  # Cambio cada ~50 velas o 2% probabilidad
            current_trend = np.random.choice([-1, 0, 1], p=[0.3, 0.4, 0.3])
            trend_persistence = 0
        
        trend_persistence += 1
        
        # Componentes del movimiento de precio
        # 1. Ruido aleatorio (movimiento browniano)
        random_component = np.random.normal(0, intraday_vol * session_factor)
        
        # 2. Componente de tendencia
        if current_trend != 0:
            trend_strength = np.random.uniform(0.0001, 0.0005)
            trend_component = current_trend * trend_strength
        else:
            trend_component = 0
        
        # 3. Mean reversion (retorno a precio base)
        distance_from_base = (current_price - base_price) / base_price
        mean_reversion = -distance_from_base * 0.002
        
        # 4. Microestructura (bid-ask bounce)
        microstructure = np.random.normal(0, intraday_vol * 0.1)
        
        # Calcular nuevo retorno
        total_return = random_component + trend_component + mean_reversion + microstructure
        
        # Aplicar el retorno
        new_price = current_price * (1 + total_return)
        
        # Mantener en rango realista
        if symbol == "EURUSD":
            new_price = max(0.9500, min(1.2500, new_price))
        
        prices.append(new_price)
        returns.append(total_return)
        trends.append(current_trend)
        current_price = new_price
    
    print(f"✅ Precios generados. Rango: {min(prices):.5f} - {max(prices):.5f}")
    
    # Generar datos OHLC realistas
    print("🔨 Generando datos OHLC...")
    ohlc_data = []
    
    for i, (date, price) in enumerate(zip(dates, prices)):
        # Parámetros para esta vela
        hour = date.hour
        volatility_mult = 1.8 if 7 <= hour <= 16 else 0.8
        
        # Tamaño del cuerpo y mechas
        body_size = abs(returns[i]) * price
        max_wick = intraday_vol * price * volatility_mult * np.random.uniform(1.2, 2.5)
        
        # Decidir si es vela alcista o bajista
        bullish = returns[i] > 0
        
        if bullish:
            # Vela verde
            open_price = price - body_size/2
            close_price = price + body_size/2
            
            # Mechas
            upper_wick = np.random.uniform(0, max_wick * 0.7)
            lower_wick = np.random.uniform(0, max_wick * 0.4)
            
            high = close_price + upper_wick
            low = open_price - lower_wick
            
        else:
            # Vela roja
            open_price = price + body_size/2
            close_price = price - body_size/2
            
            # Mechas
            upper_wick = np.random.uniform(0, max_wick * 0.4)
            lower_wick = np.random.uniform(0, max_wick * 0.7)
            
            high = open_price + upper_wick
            low = close_price - lower_wick
        
        # Asegurar consistencia OHLC
        high = max(high, open_price, close_price)
        low = min(low, open_price, close_price)
        
        # Volumen realista
        base_volume = 1500
        vol_factor = (1 + abs(returns[i]) * 100) * volatility_mult
        volume = int(base_volume * vol_factor * np.random.uniform(0.7, 1.5))
        
        ohlc_data.append({
            'datetime': date,
            'open': round(open_price, 5),
            'high': round(high, 5),
            'low': round(low, 5),
            'close': round(close_price, 5),
            'volume': volume
        })
        
        # Progreso
        if i % 5000 == 0 and i > 0:
            progress = (i / len(dates)) * 100
            print(f"   📈 Progreso: {progress:.1f}% ({i:,}/{len(dates):,} velas)")
    
    # Crear DataFrame
    df = pd.DataFrame(ohlc_data)
    
    # Guardar archivo
    filename = f"{symbol.lower()}_5min_{days}days.csv"
    df.to_csv(filename, index=False)
    
    # Estadísticas finales
    print(f"\n✅ Datos guardados en: {filename}")
    print(f"📊 Estadísticas del dataset:")
    print(f"   • Total velas: {len(df):,}")
    print(f"   • Periodo: {df['datetime'].min()} a {df['datetime'].max()}")
    print(f"   • Precio mín/máx: {df['low'].min():.5f} / {df['high'].max():.5f}")
    print(f"   • Volatilidad diaria promedio: {df['close'].pct_change().std() * np.sqrt(288) * 100:.2f}%")
    print(f"   • Tamaño archivo: {os.path.getsize(filename) / 1024 / 1024:.1f} MB")
    
    return filename

def main():
    """Función principal con menú interactivo"""
    print("=" * 60)
    print("🎯 GENERADOR DE DATOS FOREX EXTENDIDOS PARA BACKTESTING")
    print("=" * 60)
    
    # Configuraciones predefinidas
    presets = {
        "1": {"days": 30, "desc": "1 mes (pruebas rápidas)"},
        "2": {"days": 90, "desc": "3 meses (backtesting estándar)"},
        "3": {"days": 180, "desc": "6 meses (validación robusta)"},
        "4": {"days": 365, "desc": "1 año (análisis completo)"},
        "5": {"days": 730, "desc": "2 años (máxima robustez)"}
    }
    
    print("🔢 Selecciona el tamaño del dataset:")
    for key, preset in presets.items():
        velas = preset["days"] * 288
        mb_aprox = velas * 80 / 1024 / 1024  # Aproximación del tamaño
        print(f"   {key}. {preset['desc']} - ~{velas:,} velas (~{mb_aprox:.1f}MB)")
    
    print("   6. Personalizado")
    
    choice = input("\n🎯 Elige una opción (1-6): ").strip()
    
    if choice in presets:
        days = presets[choice]["days"]
        print(f"\n📅 Generando {presets[choice]['desc']}...")
    elif choice == "6":
        try:
            days = int(input("📅 Ingresa el número de días: "))
            if days < 1:
                print("⚠️  Debe ser al menos 1 día")
                return
            if days > 1000:
                print("⚠️  Máximo 1000 días (demasiado datos)")
                return
        except ValueError:
            print("❌ Número inválido")
            return
    else:
        print("❌ Opción inválida")
        return
    
    # Estimar tiempo y recursos
    velas = days * 288
    tiempo_est = velas / 10000  # Aproximadamente 10k velas por segundo
    
    print(f"\n⏱️  Tiempo estimado: ~{tiempo_est:.1f} segundos")
    print(f"💾 Espacio estimado: ~{velas * 80 / 1024 / 1024:.1f} MB")
    
    confirm = input("\n¿Continuar? (s/n): ").strip().lower()
    if confirm not in ['s', 'y', 'yes', 'si', 'sí']:
        print("❌ Cancelado")
        return
    
    # Generar datos
    start_time = datetime.now()
    filename = generate_realistic_forex_data(days=days)
    end_time = datetime.now()
    
    print(f"\n🎉 ¡Datos generados exitosamente!")
    print(f"⏱️  Tiempo transcurrido: {(end_time - start_time).total_seconds():.1f} segundos")
    print(f"📁 Archivo: {filename}")
    print(f"\n▶️  Siguiente paso: python main_backtest.py")

if __name__ == "__main__":
    main()
# main_backtest.py
import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import itertools
from collections import defaultdict
import os

# Importar el código del sistema de backtesting
# (Aquí iría todo el código del sistema que creé anteriormente)

# Indicador SuperTrend personalizado
class SuperTrend(bt.Indicator):
    lines = ('supertrend', 'trend', 'signal_bars')
    params = (
        ('period', 10),
        ('multiplier', 3.0),
    )
    
    def __init__(self):
        self.atr = bt.indicators.ATR(self.data, period=self.params.period)
        self.hl_avg = (self.data.high + self.data.low) / 2.0
        
    def next(self):
        atr_value = self.atr[0]
        hl_avg = self.hl_avg[0]
        
        upper_band = hl_avg + (self.params.multiplier * atr_value)
        lower_band = hl_avg - (self.params.multiplier * atr_value)
        
        if len(self) == 1:
            self.lines.supertrend[0] = upper_band
            self.lines.trend[0] = 1
            self.lines.signal_bars[0] = 0
        else:
            prev_supertrend = self.lines.supertrend[-1]
            prev_trend = self.lines.trend[-1]
            close = self.data.close[0]
            
            if prev_trend == 1:  # Uptrend
                if close <= lower_band:
                    self.lines.supertrend[0] = upper_band
                    self.lines.trend[0] = -1
                else:
                    self.lines.supertrend[0] = max(lower_band, prev_supertrend)
                    self.lines.trend[0] = 1
            else:  # Downtrend
                if close >= upper_band:
                    self.lines.supertrend[0] = lower_band
                    self.lines.trend[0] = 1
                else:
                    self.lines.supertrend[0] = min(upper_band, prev_supertrend)
                    self.lines.trend[0] = -1
            
            # Rastrear barras desde el cambio de señal
            current_trend = self.lines.trend[0]
            if prev_trend != current_trend:  # Cambio de tendencia
                self.lines.signal_bars[0] = 1
            else:
                self.lines.signal_bars[0] = self.lines.signal_bars[-1] + 1 if self.lines.signal_bars[-1] < 999 else 999

class BinaryOptionsStrategy(bt.Strategy):
    params = (
        # Parámetros de EMAs
        ('ema1_period', 8),
        ('ema2_period', 16),
        ('ema3_period', 24),
        
        # Parámetros de SuperTrend
        ('st_period', 10),
        ('st_multiplier', 3.0),
        
        # Parámetros de ADX
        ('adx_period', 14),
        ('adx_threshold', 25),
        
        # Parámetros de RSI
        ('rsi_period', 14),
        ('rsi_oversold', 30),
        ('rsi_overbought', 70),
        
        # Parámetros de opciones binarias
        ('expiry_minutes', 30),
        ('payout_rate', 0.92),
        ('trade_amount', 1),
        
        # Control de riesgo
        ('max_trades_per_day', 10),
        ('min_time_between_trades', 3),  # minutos
        ('supertrend_delay_bars', 4),

        # AGREGAR ESTOS PARÁMETROS AQUÍ
        ('trading_start_hour', 9),    # Hora de inicio (9 AM)
        ('trading_end_hour', 13),     # Hora de fin (1 PM)  
        ('timezone_offset', -4),      # UTC-4 para Cuba
        ('enable_time_filter', True), # Activar/desactivar filtro
        
        # Debug
        ('debug', False),
    )
    
    def __init__(self):
        # Indicadores técnicos
        self.ema1 = bt.indicators.EMA(self.data.close, period=self.params.ema1_period)
        self.ema2 = bt.indicators.EMA(self.data.close, period=self.params.ema2_period)
        self.ema3 = bt.indicators.EMA(self.data.close, period=self.params.ema3_period)
        
        self.supertrend = SuperTrend(self.data, 
                                   period=self.params.st_period,
                                   multiplier=self.params.st_multiplier)
        
        self.adx = bt.indicators.ADX(self.data, period=self.params.adx_period)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        
        # Control de trades
        self.pending_trades = []
        self.last_trade_time = None
        self.daily_trades = defaultdict(int)
        
        # Métricas
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0
        
        # Log de trades
        self.trade_log = []

    def is_trading_time(self, current_time):
        """
        Verificar si la hora actual está dentro del horario de trading
        Convierte UTC a hora local de Cuba (UTC-4)
        """
        if not self.params.enable_time_filter:
            return True
        
        # Convertir tiempo UTC a hora local de Cuba
        cuba_hour = (current_time.hour + self.params.timezone_offset) % 24
        
        # Verificar si está dentro del horario permitido
        is_valid_time = self.params.trading_start_hour <= cuba_hour < self.params.trading_end_hour
        
        if self.params.debug and not is_valid_time:
            print(f"⏰ Fuera de horario: {current_time} UTC -> {cuba_hour:02d}:XX Cuba")
        
        return is_valid_time

    def next(self):
        current_time = self.data.datetime.datetime(0)
        current_date = current_time.date()
        
        # Revisar trades que expiran
        self.check_expired_trades(current_time)
        
        # NUEVO: Verificar horario de trading PRIMERO
        if not self.is_trading_time(current_time):
            return  # Salir sin operar si está fuera de horario
        
        # Control de frecuencia de trades (código existente)
        if self.should_skip_trade(current_time, current_date):
            return
        
        # Verificar señales de entrada (código existente)
        if self.check_call_conditions():
            self.enter_binary_trade('CALL', current_time)
        elif self.check_put_conditions():
            self.enter_binary_trade('PUT', current_time)
    
    def check_call_conditions(self):
        """Condiciones para operación CALL (al alza)"""
        if len(self.data) < max(self.params.ema3_period, self.params.adx_period, self.params.rsi_period):
            return False
        
        current_price = self.data.close[0]
        
        # 1. Precio por encima de las 3 EMAs
        above_emas = (current_price > self.ema1[0] and 
                        current_price > self.ema2[0] and 
                        current_price > self.ema3[0])
        
        # 2. SuperTrend en señal de compra Y han pasado las velas requeridas
        st_signal = (self.supertrend.trend[0] == 1 and 
                    self.supertrend.signal_bars[0] >= self.params.supertrend_delay_bars)
        
        # 3. ADX muestra tendencia fuerte
        strong_trend = self.adx[0] > self.params.adx_threshold
        
        # 4. RSI no está en sobrecompra
        rsi_ok = self.rsi[0] < self.params.rsi_overbought
        
        if self.params.debug and above_emas and st_signal:
            print(f"🔍 CALL Signal Check - Price: {current_price:.5f}, EMAs OK: {above_emas}, "
                f"ST Signal: {st_signal}, ADX: {self.adx[0]:.2f}, RSI: {self.rsi[0]:.2f}, "
                f"ST Bars: {self.supertrend.signal_bars[0]}")
        
        return above_emas and st_signal and strong_trend and rsi_ok
    
    def check_put_conditions(self):
        """Condiciones para operación PUT (a la baja)"""
        if len(self.data) < max(self.params.ema3_period, self.params.adx_period, self.params.rsi_period):
            return False
        
        current_price = self.data.close[0]
        
        # 1. Precio por debajo de las 3 EMAs
        below_emas = (current_price < self.ema1[0] and 
                        current_price < self.ema2[0] and 
                        current_price < self.ema3[0])
        
        # 2. SuperTrend en señal de venta Y han pasado las velas requeridas
        st_signal = (self.supertrend.trend[0] == -1 and 
                    self.supertrend.signal_bars[0] >= self.params.supertrend_delay_bars)
        
        # 3. ADX muestra tendencia fuerte
        strong_trend = self.adx[0] > self.params.adx_threshold
        
        # 4. RSI no está en sobreventa
        rsi_ok = self.rsi[0] > self.params.rsi_oversold
        
        if self.params.debug and below_emas and st_signal:
            print(f"🔍 PUT Signal Check - Price: {current_price:.5f}, EMAs OK: {below_emas}, "
                f"ST Signal: {st_signal}, ADX: {self.adx[0]:.2f}, RSI: {self.rsi[0]:.2f}, "
                f"ST Bars: {self.supertrend.signal_bars[0]}")
        
        return below_emas and st_signal and strong_trend and rsi_ok
    
    def should_skip_trade(self, current_time, current_date):
        """Control de frecuencia de trades"""
        # Máximo de trades por día
        if self.daily_trades[current_date] >= self.params.max_trades_per_day:
            return True
        
        # Tiempo mínimo entre trades
        if (self.last_trade_time and 
            (current_time - self.last_trade_time).total_seconds() < 
            self.params.min_time_between_trades * 60):
            return True
        
        return False
    
    def enter_binary_trade(self, trade_type, entry_time):
        """Simular entrada de trade de opción binaria"""
        entry_price = self.data.close[0]
        expiry_time = entry_time + timedelta(minutes=self.params.expiry_minutes)
        
        # NUEVO: Verificar que la expiración también esté en horario válido
        if self.params.enable_time_filter and not self.is_trading_time(expiry_time):
            if self.params.debug:
                print(f"⚠️ Trade cancelado: expiración fuera de horario {expiry_time}")
            return
        
        # Resto del código existente...
        trade_info = {
            'type': trade_type,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'expiry_time': expiry_time,
            'amount': self.params.trade_amount
        }
        
        self.pending_trades.append(trade_info)
        self.last_trade_time = entry_time
        self.daily_trades[entry_time.date()] += 1
        
        # Log mejorado (opcional)
        if self.params.debug:
            cuba_hour = (entry_time.hour + self.params.timezone_offset) % 24
            print(f"📈 {entry_time}: {trade_type} @ {entry_price:.5f} (Cuba: {cuba_hour:02d}:{entry_time.minute:02d})")
    
    def check_expired_trades(self, current_time):
        """Verificar trades que han expirado y calcular resultados"""
        expired_trades = []
        
        for trade in self.pending_trades:
            if current_time >= trade['expiry_time']:
                expired_trades.append(trade)
        
        for trade in expired_trades:
            self.settle_trade(trade, current_time)
            self.pending_trades.remove(trade)
    
    def settle_trade(self, trade, current_time):
        """Liquidar trade expirado"""
        current_price = self.data.close[0]
        entry_price = trade['entry_price']
        trade_type = trade['type']
        amount = trade['amount']
        
        # Determinar si el trade fue ganador
        if trade_type == 'CALL':
            won = current_price > entry_price
        else:  # PUT
            won = current_price < entry_price
        
        # Calcular P&L
        if won:
            pnl = amount * self.params.payout_rate
            self.winning_trades += 1
        else:
            pnl = -amount
            self.losing_trades += 1
        
        self.total_pnl += pnl
        self.total_trades += 1
        
        # Guardar en log
        trade_result = {
            'entry_time': trade['entry_time'],
            'expiry_time': current_time,
            'type': trade_type,
            'entry_price': entry_price,
            'exit_price': current_price,
            'result': 'WIN' if won else 'LOSS',
            'pnl': pnl
        }
        self.trade_log.append(trade_result)
        
        # Log del resultado
        if self.params.debug:
            result = "WIN" if won else "LOSS"
            print(f"💰 {current_time}: {trade_type} {result} - Entry: {entry_price:.5f}, "
                  f"Exit: {current_price:.5f}, P&L: {pnl:.2f}")

class BinaryOptionsAnalyzer(bt.Analyzer):
    """Analizador personalizado para métricas de opciones binarias"""
    
    def __init__(self):
        self.results = {}
        
    def stop(self):
        strategy = self.strategy
        
        if strategy.total_trades > 0:
            win_rate = (strategy.winning_trades / strategy.total_trades) * 100
            avg_win = strategy.total_pnl / strategy.total_trades if strategy.total_trades > 0 else 0
            
            self.results = {
                'total_trades': strategy.total_trades,
                'winning_trades': strategy.winning_trades,
                'losing_trades': strategy.losing_trades,
                'win_rate': win_rate,
                'total_pnl': strategy.total_pnl,
                'avg_pnl_per_trade': avg_win,
                'profit_factor': abs(strategy.total_pnl / (strategy.losing_trades * strategy.params.trade_amount)) if strategy.losing_trades > 0 else float('inf'),
                'trade_log': strategy.trade_log
            }

def load_data(filename):
    """Cargar datos desde CSV"""
    if not os.path.exists(filename):
        print(f"❌ Archivo no encontrado: {filename}")
        return None
    
    try:
        df = pd.read_csv(filename)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        print(f"✅ Datos cargados: {len(df)} velas")
        print(f"📅 Periodo: {df.index.min()} a {df.index.max()}")
        
        return bt.feeds.PandasData(dataname=df)
    except Exception as e:
        print(f"❌ Error cargando datos: {str(e)}")
        return None

def run_single_backtest(data_feed, **params):
    """Ejecutar un backtest con parámetros específicos"""
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100.0) 
    cerebro.adddata(data_feed)
    
    # Agregar estrategia con parámetros
    cerebro.addstrategy(BinaryOptionsStrategy, **params)
    cerebro.addanalyzer(BinaryOptionsAnalyzer, _name='binary_analyzer')
    
    # Ejecutar
    results = cerebro.run()
    
    return results[0].analyzers.binary_analyzer.results

def optimize_parameters(data_feed):
    """Optimización básica de parámetros"""
    print("🔧 Iniciando optimización de parámetros...")
    
    # Parámetros a optimizar (versión reducida para velocidad)
    param_combinations = [
        # Configuración conservadora
        {'ema1_period': 8, 'ema2_period': 16, 'ema3_period': 24, 'st_multiplier': 3.0, 'expiry_minutes': 5, 'adx_threshold': 25},
        
        # Configuración agresiva
        {'ema1_period': 6, 'ema2_period': 14, 'ema3_period': 22, 'st_multiplier': 2.5, 'expiry_minutes': 3, 'adx_threshold': 20},
        
        # Configuración defensiva
        {'ema1_period': 10, 'ema2_period': 18, 'ema3_period': 26, 'st_multiplier': 3.5, 'expiry_minutes': 7, 'adx_threshold': 30},
        
        # Expiración más larga
        {'ema1_period': 8, 'ema2_period': 16, 'ema3_period': 24, 'st_multiplier': 3.0, 'expiry_minutes': 10, 'adx_threshold': 25},
    ]
    
    best_result = None
    best_params = None
    best_score = 0
    
    for i, params in enumerate(param_combinations):
        print(f"🧪 Probando configuración {i+1}/{len(param_combinations)}: {params}")
        
        result = run_single_backtest(data_feed, **params)
        
        if result and result.get('total_trades', 0) >= 10:
            # Score combinado: win_rate * total_pnl * número_de_trades
            score = result['win_rate'] * max(0, result['total_pnl']) * min(result['total_trades'] / 100, 1)
            
            print(f"   📊 Win Rate: {result['win_rate']:.1f}%, P&L: ${result['total_pnl']:.2f}, Trades: {result['total_trades']}, Score: {score:.2f}")
            
            if score > best_score:
                best_score = score
                best_result = result
                best_params = params
        else:
            print("   ⚠️ Pocos trades o resultado inválido")
    
    return best_params, best_result

def main():
    """Función principal"""
    print("=== SISTEMA DE BACKTESTING PARA OPCIONES BINARIAS ===")
    print("🎯 Estrategia: EMAs + SuperTrend + ADX + RSI")
    
    # 1. Buscar archivo de datos
    possible_files = [
        "eurusd_5min_synthetic_30days.csv",
        #"eurusd_5min_synthetic_365days.csv",
    ]
    
    data_file = None
    for filename in possible_files:
        if os.path.exists(filename):
            data_file = filename
            break
    
    if not data_file:
        print("❌ No se encontró archivo de datos. Ejecuta primero 'data_downloader.py'")
        return
    
    print(f"📂 Usando archivo: {data_file}")
    
    # 2. Cargar datos
    data_feed = load_data(data_file)
    if data_feed is None:
        return
    
    # 3. Menú de opciones
    print("\n🚀 ¿Qué quieres hacer?")
    print("1. Backtest rápido con parámetros por defecto")
    print("2. Backtest con debug activado")
    print("3. Optimización de parámetros")
    print("4. Backtest personalizado")
    
    choice = input("\nElige una opción (1-4): ").strip()
    
    if choice == "1":
        print("\n📊 Ejecutando backtest con parámetros por defecto...")
        result = run_single_backtest(data_feed)
        print_results(result)
        
    elif choice == "2":
        print("\n🔍 Ejecutando backtest con debug...")
        result = run_single_backtest(data_feed, debug=True)
        print_results(result)
        
    elif choice == "3":
        print("\n🔧 Ejecutando optimización...")
        best_params, best_result = optimize_parameters(data_feed)
        if best_result:
            print(f"\n🏆 MEJORES PARÁMETROS: {best_params}")
            print_results(best_result)
        else:
            print("❌ No se encontraron parámetros óptimos")
            
    elif choice == "4":
        print("\n⚙️ Configuración personalizada:")
        expiry = int(input("Tiempo de expiración (minutos, default=5): ") or "5")
        adx_threshold = int(input("Umbral ADX (default=25): ") or "25")
        st_multiplier = float(input("SuperTrend multiplier (default=3.0): ") or "3.0")
        
        custom_params = {
            'expiry_minutes': expiry,
            'adx_threshold': adx_threshold,
            'st_multiplier': st_multiplier,
            'debug': True
        }
        
        result = run_single_backtest(data_feed, **custom_params)
        print_results(result)

def print_results(result):
    """Mostrar resultados de forma clara"""
    if not result:
        print("❌ No hay resultados para mostrar")
        return
    
    print("\n" + "="*50)
    print("🎯 RESULTADOS DEL BACKTEST")
    print("="*50)
    
    print(f"📊 Total de trades: {result['total_trades']}")
    print(f"✅ Trades ganadores: {result['winning_trades']}")
    print(f"❌ Trades perdedores: {result['losing_trades']}")
    print(f"🎯 Win Rate: {result['win_rate']:.2f}%")
    print(f"💰 P&L Total: ${result['total_pnl']:.2f}")
    print(f"📈 P&L Promedio por trade: ${result['avg_pnl_per_trade']:.2f}")
    print(f"⚖️ Profit Factor: {result['profit_factor']:.2f}")
    
    # Análisis adicional
    if result['win_rate'] >= 60:
        print("🎉 ¡Excelente win rate!")
    elif result['win_rate'] >= 55:
        print("👍 Buen win rate")
    else:
        print("⚠️ Win rate mejorable")
    
    if result['total_pnl'] > 0:
        print("💚 Estrategia rentable")
    else:
        print("💔 Estrategia no rentable")

if __name__ == "__main__":
    main()
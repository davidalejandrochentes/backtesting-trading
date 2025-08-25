# default.py - Versión corregida
import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import itertools
from collections import defaultdict
import os

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
        # Verificar que tenemos suficientes datos
        if len(self.atr) == 0 or self.atr[0] is None:
            return
            
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
                prev_signal_bars = self.lines.signal_bars[-1] if len(self.lines.signal_bars) > 1 else 0
                self.lines.signal_bars[0] = prev_signal_bars + 1 if prev_signal_bars < 999 else 999

class BinaryOptionsStrategy(bt.Strategy):
    params = (
        # Parámetros de EMAs
        ('ema1_period', 13),
        
        # Parámetros de SuperTrend
        ('st_period', 10),
        ('st_multiplier', 3.5),
        ('supertrend_delay_bars', 3),
        
        # Parámetros de ADX
        ('adx_period', 21),
        ('adx_threshold', 30),
        
        # Parámetros de RSI
        ('rsi_period', 21),
        ('rsi_oversold', 35),
        ('rsi_overbought', 65),
        
        # Parámetros de opciones binarias
        ('expiry_minutes', 60),
        ('payout_rate', 0.70),
        ('trade_amount', 1),
        
        # Control de riesgo
        ('max_trades_per_day', 10),
        ('min_time_between_trades', 3),  # minutos

        # Parámetros de horario
        ('trading_start_hour', 8),
        ('trading_end_hour', 13),
        ('timezone_offset', -4),
        ('enable_time_filter', False),
        
        # Debug
        ('debug', False),
    )
    
    def __init__(self):
        # Verificar que los parámetros son válidos
        self.min_bars_needed = max(
            self.params.ema1_period,
            self.params.st_period,
            self.params.adx_period,
            self.params.rsi_period
        ) + 10  # Buffer adicional
        
        # Indicadores técnicos
        try:
            self.ema1 = bt.indicators.EMA(self.data.close, period=self.params.ema1_period)
            
            self.supertrend = SuperTrend(self.data, 
                                       period=self.params.st_period,
                                       multiplier=self.params.st_multiplier)
            
            self.adx = bt.indicators.ADX(self.data, period=self.params.adx_period)
            self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
            
        except Exception as e:
            print(f"❌ Error inicializando indicadores: {e}")
            raise
        
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
        """Verificar si la hora actual está dentro del horario de trading"""
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
        # Verificar que tenemos suficientes datos históricos
        if len(self.data) < self.min_bars_needed:
            return
            
        # Verificar que todos los indicadores tienen valores válidos
        try:
            if (self.ema1[0] is None or 
                self.supertrend.trend[0] is None or 
                self.adx[0] is None or 
                self.rsi[0] is None):
                return
        except (IndexError, TypeError):
            return
        
        current_time = self.data.datetime.datetime(0)
        current_date = current_time.date()
        
        # Revisar trades que expiran
        self.check_expired_trades(current_time)
        
        # Verificar horario de trading
        if not self.is_trading_time(current_time):
            return
        
        # Control de frecuencia de trades
        if self.should_skip_trade(current_time, current_date):
            return
        
        # Verificar señales de entrada
        try:
            if self.check_call_conditions():
                self.enter_binary_trade('CALL', current_time)
            elif self.check_put_conditions():
                self.enter_binary_trade('PUT', current_time)
        except Exception as e:
            if self.params.debug:
                print(f"❌ Error en señales: {e}")
    
    def check_call_conditions(self):
        """Condiciones para operación CALL (al alza)"""
        try:
            current_price = self.data.close[0]
            
            # 1. Precio por encima de EMA
            above_emas = current_price > self.ema1[0]
            
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
            
        except (IndexError, TypeError, AttributeError) as e:
            if self.params.debug:
                print(f"❌ Error en check_call_conditions: {e}")
            return False
    
    def check_put_conditions(self):
        """Condiciones para operación PUT (a la baja)"""
        try:
            current_price = self.data.close[0]
            
            # 1. Precio por debajo de EMA
            below_emas = current_price < self.ema1[0]
            
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
            
        except (IndexError, TypeError, AttributeError) as e:
            if self.params.debug:
                print(f"❌ Error en check_put_conditions: {e}")
            return False
    
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
        try:
            entry_price = self.data.close[0]
            expiry_time = entry_time + timedelta(minutes=int(self.params.expiry_minutes))
            
            # Verificar que la expiración también esté en horario válido
            if self.params.enable_time_filter and not self.is_trading_time(expiry_time):
                if self.params.debug:
                    print(f"⚠️ Trade cancelado: expiración fuera de horario {expiry_time}")
                return
            
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
            
            # Log mejorado
            if self.params.debug:
                cuba_hour = (entry_time.hour + self.params.timezone_offset) % 24
                print(f"📈 {entry_time}: {trade_type} @ {entry_price:.5f} (Cuba: {cuba_hour:02d}:{entry_time.minute:02d})")
                
        except Exception as e:
            if self.params.debug:
                print(f"❌ Error en enter_binary_trade: {e}")
    
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
        try:
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
                      
        except Exception as e:
            if self.params.debug:
                print(f"❌ Error en settle_trade: {e}")

class BinaryOptionsAnalyzer(bt.Analyzer):
    """Analizador personalizado para métricas de opciones binarias"""
    
    def __init__(self):
        self.results = {}
        
    def stop(self):
        strategy = self.strategy
        
        if strategy.total_trades > 0:
            win_rate = (strategy.winning_trades / strategy.total_trades) * 100
            avg_win = strategy.total_pnl / strategy.total_trades if strategy.total_trades > 0 else 0
            
            # Calcular profit factor más robusto
            total_losses = strategy.losing_trades * strategy.params.trade_amount
            if total_losses > 0:
                profit_factor = abs(strategy.total_pnl + total_losses) / total_losses
            else:
                profit_factor = float('inf') if strategy.total_pnl > 0 else 0
            
            self.results = {
                'total_trades': strategy.total_trades,
                'winning_trades': strategy.winning_trades,
                'losing_trades': strategy.losing_trades,
                'win_rate': win_rate,
                'total_pnl': strategy.total_pnl,
                'avg_pnl_per_trade': avg_win,
                'profit_factor': profit_factor,
                'trade_log': strategy.trade_log
            }
        else:
            # Retornar estructura vacía pero válida
            self.results = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl_per_trade': 0,
                'profit_factor': 0,
                'trade_log': []
            }

def load_data(filename):
    """Cargar datos desde CSV"""
    if not os.path.exists(filename):
        print(f"❌ Archivo no encontrado: {filename}")
        return None
    
    try:
        df = pd.read_csv(filename, 
                        names=['datetime', 'open', 'high', 'low', 'close', 'volume'],
                        sep='\t')
        
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
    try:
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(100.0) 
        cerebro.adddata(data_feed)
        
        # Agregar estrategia con parámetros
        cerebro.addstrategy(BinaryOptionsStrategy, **params)
        cerebro.addanalyzer(BinaryOptionsAnalyzer, _name='binary_analyzer')
        
        # Ejecutar
        results = cerebro.run()
        
        if results and len(results) > 0:
            analyzer = results[0].analyzers.binary_analyzer
            if hasattr(analyzer, 'results'):
                return analyzer.results
            else:
                return None
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error en run_single_backtest: {e}")
        return None

def main():
    """Función principal"""
    print("=== SISTEMA DE BACKTESTING PARA OPCIONES BINARIAS ===")
    print("🎯 Estrategia: EMAs + SuperTrend + ADX + RSI")
    
    # 1. Buscar archivo de datos
    possible_files = [
        "EURUSD5.csv",
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
    
    # 3. Ejecutar backtest con parámetros por defecto
    print("\n📊 Ejecutando backtest con parámetros por defecto...")
    result = run_single_backtest(data_feed)
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
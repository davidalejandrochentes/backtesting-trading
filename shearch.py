#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shearch.py - Búsqueda y optimización de parámetros para estrategia de opciones binarias
"""

import backtrader as bt
import pandas as pd
import numpy as np
import itertools
from collections import defaultdict
import os
from datetime import datetime
import json

# Importar componentes de default.py
from default import (
    BinaryOptionsStrategy, 
    BinaryOptionsAnalyzer, 
    load_data,
    run_single_backtest
)

class ParameterOptimizer:
    """Clase para optimización de parámetros"""
    
    def __init__(self, data_feed):
        self.data_feed = data_feed
        self.results = []
        self.best_result = None
        
    def define_parameter_ranges(self):
        """Definir rangos de parámetros para optimizar"""
        param_ranges = {
            # EMA
            'ema1_period': [5, 8, 13, 21],
            
            # SuperTrend
            'st_period': [7, 10, 14, 21],
            'st_multiplier': [2.0, 2.5, 3.0, 3.5, 4.0],
            
            # ADX
            'adx_period': [10, 14, 18, 21],
            'adx_threshold': [20, 25, 30, 35],
            
            # RSI
            'rsi_period': [9, 14, 21],
            'rsi_oversold': [25, 30, 35],
            'rsi_overbought': [65, 70, 75],
            
            # SuperTrend delay
            'supertrend_delay_bars': [1, 2, 3, 4, 5],
            
            # Opciones binarias
            'expiry_minutes': [15, 30, 60, 120],
            
            # Control de riesgo
            'max_trades_per_day': [5, 10, 15, 20],
            'min_time_between_trades': [1, 3, 5, 10],
        }
        
        return param_ranges
    
    def generate_parameter_combinations(self, max_combinations=100):
        """Generar combinaciones de parámetros (limitado para evitar explosión combinatoria)"""
        param_ranges = self.define_parameter_ranges()
        
        # Calcular total de combinaciones posibles
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        print(f"📊 Total de combinaciones posibles: {total_combinations:,}")
        
        if total_combinations <= max_combinations:
            # Si son pocas, usar todas las combinaciones
            keys = list(param_ranges.keys())
            values = list(param_ranges.values())
            combinations = list(itertools.product(*values))
            
            param_sets = []
            for combo in combinations:
                param_set = dict(zip(keys, combo))
                param_sets.append(param_set)
                
        else:
            # Si son muchas, usar muestreo aleatorio
            print(f"🎲 Usando muestreo aleatorio de {max_combinations} combinaciones")
            param_sets = []
            
            for _ in range(max_combinations):
                param_set = {}
                for param, values in param_ranges.items():
                    param_set[param] = np.random.choice(values)
                param_sets.append(param_set)
        
        return param_sets
    
    def run_optimization(self, max_combinations=50, min_trades=10):
        """Ejecutar optimización de parámetros"""
        print("\n" + "="*60)
        print("🔍 INICIANDO OPTIMIZACIÓN DE PARÁMETROS")
        print("="*60)
        
        # Generar combinaciones
        param_sets = self.generate_parameter_combinations(max_combinations)
        total_sets = len(param_sets)
        
        print(f"🧪 Probando {total_sets} combinaciones de parámetros...")
        print(f"📈 Mínimo de trades requeridos: {min_trades}")
        
        # Ejecutar backtests
        valid_results = 0
        
        for i, params in enumerate(param_sets):
            try:
                # Mostrar progreso
                progress = ((i + 1) / total_sets) * 100
                print(f"⚡ Progreso: {i+1}/{total_sets} ({progress:.1f}%)", end='\r')
                
                # Ejecutar backtest
                result = run_single_backtest(self.data_feed, **params)
                
                # Validar resultado
                if result and result.get('total_trades', 0) >= min_trades:
                    result['parameters'] = params.copy()
                    result['combination_id'] = i + 1
                    self.results.append(result)
                    valid_results += 1
                
            except Exception as e:
                continue
        
        print(f"\n✅ Optimización completada!")
        print(f"📊 Combinaciones válidas: {valid_results}/{total_sets}")
        
        if valid_results > 0:
            self.analyze_results()
        else:
            print("❌ No se obtuvieron resultados válidos")
    
    def analyze_results(self):
        """Analizar y mostrar los mejores resultados"""
        if not self.results:
            print("❌ No hay resultados para analizar")
            return
        
        # Ordenar por diferentes métricas
        by_winrate = sorted(self.results, key=lambda x: x['win_rate'], reverse=True)
        by_pnl = sorted(self.results, key=lambda x: x['total_pnl'], reverse=True)
        by_profit_factor = sorted(self.results, key=lambda x: x['profit_factor'], reverse=True)
        by_trades = sorted(self.results, key=lambda x: x['total_trades'], reverse=True)
        
        self.best_result = by_pnl[0]  # El mejor por P&L total
        
        print("\n" + "="*80)
        print("🏆 TOP 5 RESULTADOS POR DIFERENTES MÉTRICAS")
        print("="*80)
        
        # Top 5 por Win Rate
        print(f"\n📊 TOP 5 POR WIN RATE:")
        print("-" * 60)
        for i, result in enumerate(by_winrate[:5]):
            print(f"{i+1}. Win Rate: {result['win_rate']:.1f}% | "
                  f"P&L: ${result['total_pnl']:.2f} | "
                  f"Trades: {result['total_trades']} | "
                  f"ID: {result['combination_id']}")
        
        # Top 5 por P&L Total
        print(f"\n💰 TOP 5 POR P&L TOTAL:")
        print("-" * 60)
        for i, result in enumerate(by_pnl[:5]):
            print(f"{i+1}. P&L: ${result['total_pnl']:.2f} | "
                  f"Win Rate: {result['win_rate']:.1f}% | "
                  f"Trades: {result['total_trades']} | "
                  f"ID: {result['combination_id']}")
        
        # Top 5 por Profit Factor
        print(f"\n⚖️ TOP 5 POR PROFIT FACTOR:")
        print("-" * 60)
        for i, result in enumerate(by_profit_factor[:5]):
            pf = result['profit_factor']
            pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
            print(f"{i+1}. Profit Factor: {pf_str} | "
                  f"P&L: ${result['total_pnl']:.2f} | "
                  f"Win Rate: {result['win_rate']:.1f}% | "
                  f"ID: {result['combination_id']}")
        
        # Mostrar el mejor resultado en detalle
        print("\n" + "="*80)
        print("🥇 MEJOR CONFIGURACIÓN (Por P&L Total)")
        print("="*80)
        self.show_detailed_result(self.best_result)
    
    def show_detailed_result(self, result):
        """Mostrar resultado detallado"""
        if not result:
            return
        
        print(f"\n📈 MÉTRICAS DE RENDIMIENTO:")
        print(f"   💰 P&L Total: ${result['total_pnl']:.2f}")
        print(f"   🎯 Win Rate: {result['win_rate']:.1f}%")
        print(f"   📊 Total Trades: {result['total_trades']}")
        print(f"   ✅ Trades Ganadores: {result['winning_trades']}")
        print(f"   ❌ Trades Perdedores: {result['losing_trades']}")
        print(f"   📉 P&L Promedio: ${result['avg_pnl_per_trade']:.2f}")
        
        pf = result['profit_factor']
        pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"
        print(f"   ⚖️ Profit Factor: {pf_str}")
        
        print(f"\n🔧 PARÁMETROS ÓPTIMOS:")
        params = result['parameters']
        
        print(f"   📊 EMA Period: {params['ema1_period']}")
        print(f"   🌟 SuperTrend Period: {params['st_period']}")
        print(f"   🌟 SuperTrend Multiplier: {params['st_multiplier']}")
        print(f"   🌟 SuperTrend Delay Bars: {params['supertrend_delay_bars']}")
        print(f"   📈 ADX Period: {params['adx_period']}")
        print(f"   📈 ADX Threshold: {params['adx_threshold']}")
        print(f"   🔄 RSI Period: {params['rsi_period']}")
        print(f"   🔄 RSI Oversold: {params['rsi_oversold']}")
        print(f"   🔄 RSI Overbought: {params['rsi_overbought']}")
        print(f"   ⏰ Expiry Minutes: {params['expiry_minutes']}")
        print(f"   🛡️ Max Trades/Day: {params['max_trades_per_day']}")
        print(f"   ⏳ Min Time Between Trades: {params['min_time_between_trades']} min")
    
    def save_results(self, filename="optimization_results.json"):
        """Guardar resultados en archivo JSON"""
        if not self.results:
            print("❌ No hay resultados para guardar")
            return
        
        try:
            # Preparar datos para guardar
            save_data = {
                'optimization_date': datetime.now().isoformat(),
                'total_combinations_tested': len(self.results),
                'best_result': self.best_result,
                'all_results': self.results[:20]  # Solo los primeros 20 para no hacer el archivo muy grande
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 Resultados guardados en: {filename}")
            
        except Exception as e:
            print(f"❌ Error guardando resultados: {e}")

def run_parameter_search():
    """Función principal para búsqueda de parámetros"""
    print("🔍 BÚSQUEDA Y OPTIMIZACIÓN DE PARÁMETROS")
    print("=" * 50)
    
    # 1. Buscar archivo de datos
    possible_files = ["EURUSD5.csv"]
    
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
    
    # 3. Configurar optimización
    print(f"\n🎛️ CONFIGURACIÓN DE LA OPTIMIZACIÓN:")
    
    try:
        max_combinations = int(input("🧪 Máximo de combinaciones a probar (por defecto 50): ") or 50)
        min_trades = int(input("📈 Mínimo de trades requeridos (por defecto 10): ") or 10)
    except ValueError:
        max_combinations = 50
        min_trades = 10
        print("⚠️ Usando valores por defecto")
    
    # 4. Ejecutar optimización
    optimizer = ParameterOptimizer(data_feed)
    optimizer.run_optimization(max_combinations=max_combinations, min_trades=min_trades)
    
    # 5. Guardar resultados
    if optimizer.results:
        save_choice = input(f"\n💾 ¿Guardar resultados en archivo? (y/N): ").strip().lower()
        if save_choice in ['y', 'yes', 'sí', 'si']:
            optimizer.save_results()
    
    return optimizer

def main():
    """Función principal del módulo"""
    run_parameter_search()

if __name__ == "__main__":
    main()
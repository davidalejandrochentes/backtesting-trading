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
import random  # Importar random al inicio

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
            'ema1_period': [5, 8, 13, 21],
            'st_period': [7, 10, 14, 21],
            'st_multiplier': [2.0, 2.5, 3.0, 3.5, 4.0],
            'adx_period': [14, 21],
            'adx_threshold': [20, 25, 30],
            'rsi_period': [14, 21],
            'rsi_oversold': [30, 35],
            'rsi_overbought': [65, 70],
            'supertrend_delay_bars': [3, 4, 5],
            'expiry_minutes': [15, 30, 45, 60, 90, 120],
            'max_trades_per_day': [8, 12, 16],
            'min_time_between_trades': [3, 5, 8],
        }
        
        return param_ranges
    
    def generate_parameter_combinations(self, max_combinations=100, use_random_seed=True):
        """Generar combinaciones de parámetros (limitado para evitar explosión combinatoria)"""
        param_ranges = self.define_parameter_ranges()
        
        # Calcular total de combinaciones posibles
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        print(f"📊 Total de combinaciones posibles: {total_combinations:,}")
        
        if total_combinations <= max_combinations:
            # Si son pocas, usar todas las combinaciones
            print(f"✅ Usando todas las {total_combinations} combinaciones disponibles")
            keys = list(param_ranges.keys())
            values = list(param_ranges.values())
            combinations = list(itertools.product(*values))
            
            param_sets = []
            for combo in combinations:
                param_set = {}
                for key, value in zip(keys, combo):
                    # Convertir a tipos Python nativos
                    if isinstance(value, (np.integer, np.int64, np.int32)):
                        param_set[key] = int(value)
                    elif isinstance(value, (np.floating, np.float64, np.float32)):
                        param_set[key] = float(value)
                    else:
                        param_set[key] = value
                param_sets.append(param_set)
                
        else:
            # Si son muchas, usar muestreo aleatorio
            print(f"🎲 Usando muestreo aleatorio de {max_combinations} combinaciones")
            param_sets = []
            
            # CORRECCIÓN PRINCIPAL: Inicializar semilla aleatoria UNA SOLA VEZ
            # y usar un timestamp o None para hacerlo verdaderamente aleatorio
            if use_random_seed:
                # Usar timestamp para semilla única cada vez que se ejecuta
                seed = int(datetime.now().timestamp() * 1000) % 2**32
                random.seed(seed)
                np.random.seed(seed)
                print(f"🔑 Usando semilla aleatoria: {seed}")
            else:
                # Para pruebas reproducibles
                random.seed(42)
                np.random.seed(42)
                print(f"🔑 Usando semilla fija: 42")
            
            # Generar todas las combinaciones posibles primero
            keys = list(param_ranges.keys())
            values = list(param_ranges.values())
            all_combinations = list(itertools.product(*values))
            
            # Seleccionar aleatoriamente sin repetición
            if len(all_combinations) > max_combinations:
                selected_indices = random.sample(range(len(all_combinations)), max_combinations)
                selected_combinations = [all_combinations[i] for i in selected_indices]
            else:
                selected_combinations = all_combinations
            
            # Convertir a diccionarios de parámetros
            for combo in selected_combinations:
                param_set = {}
                for key, value in zip(keys, combo):
                    # Convertir a tipos Python nativos
                    if isinstance(value, (np.integer, np.int64, np.int32)):
                        param_set[key] = int(value)
                    elif isinstance(value, (np.floating, np.float64, np.float32)):
                        param_set[key] = float(value)
                    else:
                        param_set[key] = value
                param_sets.append(param_set)
            
            print(f"✅ Generadas {len(param_sets)} combinaciones únicas")
        
        return param_sets
    
    def format_result_summary(self, result):
        """Formatear un resumen limpio del resultado"""
        if not result or not isinstance(result, dict):
            return "Resultado inválido"
        
        return (f"Trades: {result.get('total_trades', 0)} | "
                f"Win Rate: {result.get('win_rate', 0):.1f}% | "
                f"P&L: ${result.get('total_pnl', 0):.2f}")
    
    def run_optimization(self, max_combinations=50, min_trades=10, verbose=False, use_random_seed=True):
        """Ejecutar optimización de parámetros"""
        print("\n" + "="*60)
        print("🔍 INICIANDO OPTIMIZACIÓN DE PARÁMETROS")
        print("="*60)
        
        # Generar combinaciones con opción de semilla aleatoria
        param_sets = self.generate_parameter_combinations(max_combinations, use_random_seed)
        total_sets = len(param_sets)
        
        # Verificar que realmente tenemos combinaciones
        if total_sets == 0:
            print("❌ No se pudieron generar combinaciones de parámetros")
            return
        
        print(f"🧪 Probando {total_sets} combinaciones de parámetros...")
        print(f"📈 Mínimo de trades requeridos: {min_trades}")
        
        # Ejecutar backtests
        valid_results = 0
        error_count = 0
        
        # Para mostrar progreso cada 10%
        progress_points = [max(1, int(total_sets * p / 10)) for p in range(1, 11)]
        
        for i, params in enumerate(param_sets):
            try:
                # Mostrar progreso solo en ciertos puntos
                if (i + 1) in progress_points or i == 0:
                    progress = ((i + 1) / total_sets) * 100
                    print(f"⚡ Progreso: {progress:.0f}% - Válidos: {valid_results}/{i+1}")
                
                # Debug detallado solo si verbose=True y para las primeras 3 combinaciones
                if verbose and i < 3:
                    print(f"\n🔧 Probando combinación {i+1}:")
                    for key, value in params.items():
                        print(f"   {key}: {value}")
                
                # Ejecutar backtest
                result = run_single_backtest(self.data_feed, **params)
                
                # Debug del resultado solo si verbose=True
                if verbose and i < 3:
                    print(f"📊 Resultado: {self.format_result_summary(result)}")
                
                # Validar resultado
                if result and isinstance(result, dict):
                    total_trades = result.get('total_trades', 0)
                    if total_trades >= min_trades:
                        # Limpiar el resultado antes de guardarlo (eliminar lista de trades)
                        clean_result = {k: v for k, v in result.items() if k != 'trades'}
                        clean_result['parameters'] = params.copy()
                        clean_result['combination_id'] = i + 1
                        self.results.append(clean_result)
                        valid_results += 1
                        
                        if verbose and i < 3:
                            print(f"✅ Combinación {i+1} válida: {total_trades} trades")
                    else:
                        if verbose and i < 3:
                            print(f"❌ Combinación {i+1} rechazada: solo {total_trades} trades (mínimo {min_trades})")
                else:
                    error_count += 1
                    if verbose and i < 3:
                        print(f"❌ Combinación {i+1} falló: resultado nulo o inválido")
                
            except Exception as e:
                error_count += 1
                if verbose and i < 3:
                    print(f"❌ Error en combinación {i+1}: {str(e)}")
                continue
        
        # Progreso final
        print(f"⚡ Progreso: 100% - Válidos: {valid_results}/{total_sets}")
        
        print(f"\n✅ Optimización completada!")
        print(f"📊 Combinaciones válidas: {valid_results}/{total_sets}")
        if error_count > 0:
            print(f"⚠️ Errores encontrados: {error_count}")
        
        if valid_results > 0:
            self.analyze_results()
        else:
            print("❌ No se obtuvieron resultados válidos")
            print("\n🔍 DIAGNÓSTICO:")
            print("- Verifica que los parámetros generen señales de trading")
            print("- Reduce el mínimo de trades requeridos")
            print("- Aumenta el número de combinaciones a probar")
            print("- Revisa que los datos tengan suficiente historia")
    
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
        
        # Criterio: Mejor P&L Total (más rentable)
        self.best_result = by_pnl[0]  # La configuración más rentable
        print(f"🎯 Criterio: Mayor P&L Total (Más Rentable)")
        
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
    
    def save_results(self, filename=None):
        """Guardar resultados en archivo JSON con nombre único"""
        if not self.results:
            print("❌ No hay resultados para guardar")
            return
        
        try:
            # Generar nombre de archivo único si no se proporciona
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"optimization_results_{timestamp}.json"
            
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

def run_parameter_search(verbose=False):
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
        max_combinations = int(input("🧪 Máximo de combinaciones a probar (por defecto 20): ") or 20)
        min_trades = int(input("📈 Mínimo de trades requeridos (por defecto 5): ") or 5)
        
        # Preguntar si quiere modo verbose
        verbose_input = input("🔍 ¿Mostrar información detallada de debug? (y/N): ").strip().lower()
        verbose = verbose_input in ['y', 'yes', 'sí', 'si']
        
        # NUEVA OPCIÓN: Preguntar si quiere resultados aleatorios o reproducibles
        random_input = input("🎲 ¿Usar selección aleatoria de parámetros? (Y/n): ").strip().lower()
        use_random = random_input not in ['n', 'no']
        
        if not use_random:
            print("🔒 Usando selección fija (reproducible)")
        else:
            print("🎲 Usando selección aleatoria (resultados diferentes cada vez)")
        
    except ValueError:
        max_combinations = 20
        min_trades = 5
        verbose = False
        use_random = True
        print("⚠️ Usando valores por defecto")
    
    # 4. Ejecutar optimización
    optimizer = ParameterOptimizer(data_feed)
    optimizer.run_optimization(max_combinations=max_combinations, 
                             min_trades=min_trades, 
                             verbose=verbose,
                             use_random_seed=use_random)
    
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
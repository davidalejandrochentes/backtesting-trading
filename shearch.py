#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shearch_optimized.py - Búsqueda optimizada de parámetros con mejor rendimiento
"""

import backtrader as bt
import pandas as pd
import numpy as np
import itertools
from collections import defaultdict
import os
from datetime import datetime
import json
import random
import heapq
from typing import Dict, List, Tuple, Optional

# Importar componentes de default.py
from default import (
    BinaryOptionsStrategy, 
    BinaryOptionsAnalyzer, 
    load_data,
    run_single_backtest
)

class OptimizedResult:
    """Clase ligera para almacenar solo métricas esenciales"""
    __slots__ = ['win_rate', 'total_pnl', 'profit_factor', 'total_trades', 
                 'winning_trades', 'losing_trades', 'parameters', 'combination_id']
    
    def __init__(self, result_dict: Dict, parameters: Dict, combo_id: int):
        self.win_rate = result_dict.get('win_rate', 0)
        self.total_pnl = result_dict.get('total_pnl', 0)
        self.profit_factor = result_dict.get('profit_factor', 0)
        self.total_trades = result_dict.get('total_trades', 0)
        self.winning_trades = result_dict.get('winning_trades', 0)
        self.losing_trades = result_dict.get('losing_trades', 0)
        self.parameters = parameters.copy()
        self.combination_id = combo_id
    
    def to_dict(self) -> Dict:
        """Convertir a diccionario para serialización"""
        return {
            'win_rate': self.win_rate,
            'total_pnl': self.total_pnl,
            'profit_factor': self.profit_factor,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'parameters': self.parameters,
            'combination_id': self.combination_id
        }
    
    def score(self, weight_winrate=0.3, weight_pnl=0.4, weight_pf=0.3) -> float:
        """Calcular un score ponderado para rankear resultados"""
        # Normalizar valores
        norm_winrate = min(self.win_rate / 100, 1.0)  # 0-1
        norm_pnl = min(max(self.total_pnl / 100, -1), 1)  # -1 a 1, cap en 100
        norm_pf = min(self.profit_factor / 5, 1.0) if self.profit_factor != float('inf') else 1.0
        
        # Score ponderado
        return (weight_winrate * norm_winrate + 
                weight_pnl * norm_pnl + 
                weight_pf * norm_pf)


class TopResultsTracker:
    """Mantiene solo los TOP N mejores resultados eficientemente"""
    
    def __init__(self, max_results: int = 10):
        self.max_results = max_results
        self.results_by_winrate = []  # Min heap invertido (negativo)
        self.results_by_pnl = []      # Min heap invertido
        self.results_by_score = []    # Min heap invertido
        self.all_ids = set()          # Para evitar duplicados
        
    def add_result(self, result: OptimizedResult):
        """Agregar resultado si está entre los mejores"""
        if result.combination_id in self.all_ids:
            return
        
        score = result.score()
        
        # Mantener top por win rate
        if len(self.results_by_winrate) < self.max_results:
            heapq.heappush(self.results_by_winrate, (-result.win_rate, result))
        elif result.win_rate > -self.results_by_winrate[0][0]:
            heapq.heapreplace(self.results_by_winrate, (-result.win_rate, result))
        
        # Mantener top por P&L
        if len(self.results_by_pnl) < self.max_results:
            heapq.heappush(self.results_by_pnl, (-result.total_pnl, result))
        elif result.total_pnl > -self.results_by_pnl[0][0]:
            heapq.heapreplace(self.results_by_pnl, (-result.total_pnl, result))
        
        # Mantener top por score combinado
        if len(self.results_by_score) < self.max_results:
            heapq.heappush(self.results_by_score, (-score, result))
        elif score > -self.results_by_score[0][0]:
            heapq.heapreplace(self.results_by_score, (-score, result))
        
        self.all_ids.add(result.combination_id)
    
    def get_top_results(self) -> Dict[str, List[OptimizedResult]]:
        """Obtener los mejores resultados organizados"""
        return {
            'by_winrate': sorted([r for _, r in self.results_by_winrate], 
                                key=lambda x: x.win_rate, reverse=True),
            'by_pnl': sorted([r for _, r in self.results_by_pnl], 
                           key=lambda x: x.total_pnl, reverse=True),
            'by_score': sorted([r for _, r in self.results_by_score], 
                             key=lambda x: x.score(), reverse=True)
        }
    
    def get_absolute_best(self) -> Optional[OptimizedResult]:
        """Obtener el mejor resultado por score combinado"""
        if self.results_by_score:
            return max([r for _, r in self.results_by_score], key=lambda x: x.score())
        return None


class OptimizedParameterSearch:
    """Optimizador de parámetros con mejor rendimiento"""
    
    def __init__(self, data_feed, max_top_results: int = 10):
        self.data_feed = data_feed
        self.tracker = TopResultsTracker(max_top_results)
        self.valid_count = 0
        self.total_tested = 0
        
    def define_parameter_ranges(self) -> Dict:
        """Definir rangos de parámetros optimizados"""
        # Rangos más acotados para búsqueda más eficiente
        param_ranges = {
            'ema1_period': [5, 8, 13, 21],
            'st_period': [10, 14, 21],  # Reducido
            'st_multiplier': [2.5, 3.0, 3.5],  # Reducido
            'adx_period': [14, 21],
            'adx_threshold': [25, 30],  # Reducido
            'rsi_period': [14, 21],
            'rsi_oversold': [30, 35],
            'rsi_overbought': [65, 70],
            'supertrend_delay_bars': [3, 4, 5],
            'expiry_minutes': [30, 60, 90],  # Reducido
            'max_trades_per_day': [10, 14],  # Reducido
            'min_time_between_trades': [3, 5],  # Reducido
        }
        return param_ranges
    
    def generate_smart_combinations(self, max_combinations: int = 100) -> List[Dict]:
        """
        Generar combinaciones inteligentes priorizando valores prometedores
        """
        param_ranges = self.define_parameter_ranges()
        
        # Calcular total de combinaciones
        total_combinations = 1
        for values in param_ranges.values():
            total_combinations *= len(values)
        
        print(f"📊 Total de combinaciones posibles: {total_combinations:,}")
        
        if total_combinations <= max_combinations:
            # Si son pocas, usar todas
            keys = list(param_ranges.keys())
            values = list(param_ranges.values())
            combinations = list(itertools.product(*values))
            
            param_sets = []
            for combo in combinations:
                param_set = {key: self._convert_value(value) 
                           for key, value in zip(keys, combo)}
                param_sets.append(param_set)
        else:
            # Muestreo estratificado inteligente
            print(f"🎯 Usando muestreo estratificado de {max_combinations} combinaciones")
            
            # Semilla para reproducibilidad opcional
            seed = int(datetime.now().timestamp() * 1000) % 2**32
            random.seed(seed)
            np.random.seed(seed)
            
            param_sets = []
            
            # Generar combinaciones base prometedoras
            base_combinations = self._generate_promising_base()
            
            # Completar con variaciones aleatorias
            remaining = max_combinations - len(base_combinations)
            if remaining > 0:
                random_combinations = self._generate_random_combinations(
                    param_ranges, remaining, exclude=base_combinations
                )
                param_sets = base_combinations + random_combinations
            else:
                param_sets = base_combinations[:max_combinations]
        
        print(f"✅ Generadas {len(param_sets)} combinaciones únicas")
        return param_sets
    
    def _generate_promising_base(self) -> List[Dict]:
        """Generar combinaciones base que suelen funcionar bien"""
        promising_sets = [
            # Configuración conservadora
            {
                'ema1_period': 13, 'st_period': 14, 'st_multiplier': 3.0,
                'adx_period': 21, 'adx_threshold': 25, 'rsi_period': 14,
                'rsi_oversold': 30, 'rsi_overbought': 70,
                'supertrend_delay_bars': 4, 'expiry_minutes': 60,
                'max_trades_per_day': 10, 'min_time_between_trades': 5
            },
            # Configuración agresiva
            {
                'ema1_period': 8, 'st_period': 10, 'st_multiplier': 2.5,
                'adx_period': 14, 'adx_threshold': 30, 'rsi_period': 14,
                'rsi_oversold': 35, 'rsi_overbought': 65,
                'supertrend_delay_bars': 3, 'expiry_minutes': 30,
                'max_trades_per_day': 14, 'min_time_between_trades': 3
            },
            # Configuración balanceada
            {
                'ema1_period': 13, 'st_period': 10, 'st_multiplier': 3.0,
                'adx_period': 14, 'adx_threshold': 25, 'rsi_period': 21,
                'rsi_oversold': 35, 'rsi_overbought': 65,
                'supertrend_delay_bars': 4, 'expiry_minutes': 60,
                'max_trades_per_day': 10, 'min_time_between_trades': 3
            },
        ]
        return promising_sets
    
    def _generate_random_combinations(self, param_ranges: Dict, count: int, 
                                    exclude: List[Dict]) -> List[Dict]:
        """Generar combinaciones aleatorias excluyendo las ya existentes"""
        exclude_set = {str(sorted(d.items())) for d in exclude}
        
        keys = list(param_ranges.keys())
        values = list(param_ranges.values())
        all_combinations = list(itertools.product(*values))
        
        random.shuffle(all_combinations)
        
        param_sets = []
        for combo in all_combinations:
            param_dict = {key: self._convert_value(value) 
                         for key, value in zip(keys, combo)}
            
            # Verificar que no esté en exclude
            if str(sorted(param_dict.items())) not in exclude_set:
                param_sets.append(param_dict)
                if len(param_sets) >= count:
                    break
        
        return param_sets
    
    def _convert_value(self, value):
        """Convertir valores numpy a tipos Python nativos"""
        if isinstance(value, (np.integer, np.int64, np.int32)):
            return int(value)
        elif isinstance(value, (np.floating, np.float64, np.float32)):
            return float(value)
        return value
    
    def run_optimized_search(self, max_combinations: int = 50, 
                           min_trades: int = 10, 
                           min_win_rate: float = 50.0,
                           verbose: bool = False) -> Dict:
        """
        Ejecutar búsqueda optimizada con evaluación temprana
        """
        print("\n" + "="*60)
        print("🚀 BÚSQUEDA OPTIMIZADA DE PARÁMETROS")
        print("="*60)
        
        # Generar combinaciones inteligentes
        param_sets = self.generate_smart_combinations(max_combinations)
        total_sets = len(param_sets)
        
        if total_sets == 0:
            print("❌ No se pudieron generar combinaciones")
            return {}
        
        print(f"🧪 Probando {total_sets} combinaciones")
        print(f"📈 Filtros: Min trades={min_trades}, Min win rate={min_win_rate}%")
        
        # Variables para tracking
        start_time = datetime.now()
        progress_points = [max(1, int(total_sets * p / 10)) for p in range(1, 11)]
        early_stop_count = 0
        
        for i, params in enumerate(param_sets):
            self.total_tested += 1
            
            # Mostrar progreso
            if (i + 1) in progress_points or i == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total_sets - i - 1) / rate if rate > 0 else 0
                
                print(f"⚡ Progreso: {((i+1)/total_sets)*100:.0f}% | "
                      f"Válidos: {self.valid_count}/{i+1} | "
                      f"Vel: {rate:.1f}/s | ETA: {eta:.0f}s")
            
            try:
                # Ejecutar backtest (sin almacenar trades)
                result = self._run_lightweight_backtest(params)
                
                if result:
                    # Evaluación temprana
                    if result['total_trades'] < min_trades:
                        early_stop_count += 1
                        continue
                    
                    if result['win_rate'] < min_win_rate:
                        early_stop_count += 1
                        continue
                    
                    # Si pasa los filtros, crear resultado optimizado
                    opt_result = OptimizedResult(result, params, i + 1)
                    self.tracker.add_result(opt_result)
                    self.valid_count += 1
                    
                    if verbose and self.valid_count <= 3:
                        print(f"  ✅ #{i+1} válido: WR={opt_result.win_rate:.1f}%, "
                              f"P&L=${opt_result.total_pnl:.2f}")
                
            except Exception as e:
                if verbose:
                    print(f"  ❌ Error en #{i+1}: {str(e)}")
                continue
        
        # Estadísticas finales
        elapsed_total = (datetime.now() - start_time).total_seconds()
        print(f"\n✅ Búsqueda completada en {elapsed_total:.1f} segundos")
        print(f"📊 Combinaciones válidas: {self.valid_count}/{total_sets}")
        print(f"⏭️ Descartadas por evaluación temprana: {early_stop_count}")
        
        # Mostrar resultados
        if self.valid_count > 0:
            return self._show_optimized_results()
        else:
            print("❌ No se encontraron configuraciones válidas")
            return {}
    
    def _run_lightweight_backtest(self, params: Dict) -> Optional[Dict]:
        """
        Ejecutar backtest sin almacenar trades individuales
        """
        # Agregar flag para no guardar trades
        lightweight_params = params.copy()
        lightweight_params['debug'] = False  # Desactivar debug
        
        # Ejecutar backtest normal (la optimización está en no procesar después)
        result = run_single_backtest(self.data_feed, **lightweight_params)
        
        # Si hay resultado, eliminar el trade_log para ahorrar memoria
        if result and 'trade_log' in result:
            del result['trade_log']
        
        return result
    
    def _show_optimized_results(self) -> Dict:
        """Mostrar los mejores resultados de forma organizada"""
        top_results = self.tracker.get_top_results()
        best_overall = self.tracker.get_absolute_best()
        
        print("\n" + "="*80)
        print("🏆 MEJORES CONFIGURACIONES ENCONTRADAS")
        print("="*80)
        
        # Top 5 por Win Rate
        print("\n📊 TOP 5 POR WIN RATE:")
        print("-" * 60)
        for i, result in enumerate(top_results['by_winrate'][:5]):
            print(f"{i+1}. WR: {result.win_rate:.1f}% | "
                  f"P&L: ${result.total_pnl:.2f} | "
                  f"Trades: {result.total_trades} | "
                  f"Score: {result.score():.3f}")
        
        # Top 5 por P&L
        print("\n💰 TOP 5 POR P&L TOTAL:")
        print("-" * 60)
        for i, result in enumerate(top_results['by_pnl'][:5]):
            print(f"{i+1}. P&L: ${result.total_pnl:.2f} | "
                  f"WR: {result.win_rate:.1f}% | "
                  f"Trades: {result.total_trades} | "
                  f"Score: {result.score():.3f}")
        
        # Top 5 por Score Combinado
        print("\n⭐ TOP 5 POR SCORE COMBINADO:")
        print("-" * 60)
        for i, result in enumerate(top_results['by_score'][:5]):
            print(f"{i+1}. Score: {result.score():.3f} | "
                  f"WR: {result.win_rate:.1f}% | "
                  f"P&L: ${result.total_pnl:.2f} | "
                  f"Trades: {result.total_trades}")
        
        # Mejor configuración absoluta
        if best_overall:
            print("\n" + "="*80)
            print("🥇 MEJOR CONFIGURACIÓN ABSOLUTA (Score Combinado)")
            print("="*80)
            self._show_detailed_result(best_overall)
        
        return {
            'best_overall': best_overall.to_dict() if best_overall else None,
            'top_by_winrate': [r.to_dict() for r in top_results['by_winrate'][:5]],
            'top_by_pnl': [r.to_dict() for r in top_results['by_pnl'][:5]],
            'top_by_score': [r.to_dict() for r in top_results['by_score'][:5]]
        }
    
    def _show_detailed_result(self, result: OptimizedResult):
        """Mostrar detalles de un resultado específico"""
        print(f"\n📈 MÉTRICAS DE RENDIMIENTO:")
        print(f"   💰 P&L Total: ${result.total_pnl:.2f}")
        print(f"   🎯 Win Rate: {result.win_rate:.1f}%")
        print(f"   📊 Total Trades: {result.total_trades}")
        print(f"   ✅ Trades Ganadores: {result.winning_trades}")
        print(f"   ❌ Trades Perdedores: {result.losing_trades}")
        print(f"   ⭐ Score Combinado: {result.score():.3f}")
        
        pf_str = f"{result.profit_factor:.2f}" if result.profit_factor != float('inf') else "∞"
        print(f"   ⚖️ Profit Factor: {pf_str}")
        
        print(f"\n🔧 PARÁMETROS ÓPTIMOS:")
        params = result.parameters
        
        print(f"   📊 EMA Period: {params['ema1_period']}")
        print(f"   🌟 SuperTrend Period: {params['st_period']}")
        print(f"   🌟 SuperTrend Multiplier: {params['st_multiplier']}")
        print(f"   🌟 SuperTrend Delay: {params['supertrend_delay_bars']} bars")
        print(f"   📈 ADX Period: {params['adx_period']}")
        print(f"   📈 ADX Threshold: {params['adx_threshold']}")
        print(f"   🔄 RSI Period: {params['rsi_period']}")
        print(f"   🔄 RSI Oversold: {params['rsi_oversold']}")
        print(f"   🔄 RSI Overbought: {params['rsi_overbought']}")
        print(f"   ⏰ Expiry Minutes: {params['expiry_minutes']}")
        print(f"   🛡️ Max Trades/Day: {params['max_trades_per_day']}")
        print(f"   ⏳ Min Time Between: {params['min_time_between_trades']} min")
    
    def save_optimized_results(self, results: Dict, filename: Optional[str] = None):
        """Guardar solo los mejores resultados"""
        if not results:
            print("❌ No hay resultados para guardar")
            return
        
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"optimized_results_{timestamp}.json"
            
            save_data = {
                'optimization_date': datetime.now().isoformat(),
                'total_tested': self.total_tested,
                'valid_found': self.valid_count,
                'results': results
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 Resultados guardados en: {filename}")
            
        except Exception as e:
            print(f"❌ Error guardando: {e}")


def main():
    """Función principal optimizada"""
    print("🚀 BÚSQUEDA OPTIMIZADA DE PARÁMETROS")
    print("=" * 50)
    
    # 1. Buscar archivo de datos
    possible_files = ["EURUSD5.csv"]
    
    data_file = None
    for filename in possible_files:
        if os.path.exists(filename):
            data_file = filename
            break
    
    if not data_file:
        print("❌ No se encontró archivo de datos")
        return
    
    print(f"📂 Usando archivo: {data_file}")
    
    # 2. Cargar datos
    data_feed = load_data(data_file)
    if data_feed is None:
        return
    
    # 3. Configurar búsqueda optimizada
    print(f"\n🎛️ CONFIGURACIÓN DE LA BÚSQUEDA OPTIMIZADA:")
    
    try:
        max_combinations = int(input("🧪 Máximo de combinaciones (default 50): ") or 50)
        min_trades = int(input("📈 Mínimo de trades (default 10): ") or 10)
        min_win_rate = float(input("🎯 Win rate mínimo % (default 50): ") or 50)
        max_top = int(input("🏆 Cantidad de mejores a mantener (default 10): ") or 10)
        
        verbose_input = input("🔍 ¿Modo verbose? (y/N): ").strip().lower()
        verbose = verbose_input in ['y', 'yes', 'sí', 'si']
        
    except ValueError:
        max_combinations = 50
        min_trades = 10
        min_win_rate = 50.0
        max_top = 10
        verbose = False
        print("⚠️ Usando valores por defecto")
    
    # 4. Ejecutar búsqueda optimizada
    optimizer = OptimizedParameterSearch(data_feed, max_top_results=max_top)
    results = optimizer.run_optimized_search(
        max_combinations=max_combinations,
        min_trades=min_trades,
        min_win_rate=min_win_rate,
        verbose=verbose
    )
    
    # 5. Guardar resultados si hay
    if results:
        save_choice = input(f"\n💾 ¿Guardar resultados? (y/N): ").strip().lower()
        if save_choice in ['y', 'yes', 'sí', 'si']:
            optimizer.save_optimized_results(results)
    
    print("\n✨ Proceso completado")

def run_parameter_search():
    """Función wrapper para ejecutar desde main_backtest.py"""
    return main()

if __name__ == "__main__":
    main()
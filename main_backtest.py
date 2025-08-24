#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main_backtest.py - Script principal con menú de opciones
"""

import sys
import os
from default import main as run_default_backtest
from shearch import run_parameter_search

def show_menu():
    """Mostrar menú principal"""
    print("\n" + "="*60)
    print("🎯 SISTEMA DE BACKTESTING PARA OPCIONES BINARIAS")
    print("="*60)
    print()
    print("Selecciona una opción:")
    print("1️⃣  Ejecutar backtest con parámetros por defecto")
    print("2️⃣  Búsqueda y optimización de parámetros")
    print("0️⃣  Salir")
    print()
    print("-" * 60)

def get_user_choice():
    """Obtener y validar la elección del usuario"""
    while True:
        try:
            choice = input("👉 Ingresa tu opción (0-2): ").strip()
            
            if choice in ['0', '1', '2']:
                return int(choice)
            else:
                print("❌ Opción inválida. Por favor ingresa 0, 1 o 2.")
                
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta luego!")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Error: {e}")

def option_1_default_backtest():
    """Opción 1: Ejecutar backtest con parámetros por defecto"""
    print("\n" + "="*50)
    print("🚀 EJECUTANDO BACKTEST CON PARÁMETROS POR DEFECTO")
    print("="*50)
    
    try:
        # Ejecutar la función principal del archivo default.py
        run_default_backtest()
    except Exception as e:
        print(f"❌ Error ejecutando backtest: {e}")
        return False
    
    return True

def option_2_parameter_search():
    """Opción 2: Búsqueda y optimización de parámetros"""
    print("\n" + "="*50)
    print("🔍 BÚSQUEDA Y OPTIMIZACIÓN DE PARÁMETROS")
    print("="*50)
    
    try:
        # Ejecutar la optimización de parámetros
        optimizer = run_parameter_search()
        return True
    except Exception as e:
        print(f"❌ Error en optimización: {e}")
        return False

def main():
    """Función principal del script"""
    try:
        while True:
            show_menu()
            choice = get_user_choice()
            
            if choice == 0:
                print("\n👋 ¡Gracias por usar el sistema de backtesting!")
                print("💡 ¡Que tengas trades exitosos!")
                break
                
            elif choice == 1:
                success = option_1_default_backtest()
                if success:
                    input("\n📱 Presiona Enter para volver al menú principal...")
                    
            elif choice == 2:
                option_2_parameter_search()
            
    except KeyboardInterrupt:
        print("\n\n👋 ¡Hasta luego!")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
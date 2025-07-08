#!/usr/bin/env python3
# create_init_files.py - Cria arquivos __init__.py necessários

import os

def create_init_file(directory):
    """Cria arquivo __init__.py em um diretório se não existir"""
    init_path = os.path.join(directory, '__init__.py')
    
    if not os.path.exists(init_path):
        try:
            with open(init_path, 'w', encoding='utf-8') as f:
                f.write(f'# {directory}/__init__.py\n')
                f.write(f'# Este arquivo marca "{directory}" como um pacote Python.\n')
            print(f"✅ Criado: {init_path}")
            return True
        except Exception as e:
            print(f"❌ Erro ao criar {init_path}: {e}")
            return False
    else:
        print(f"✅ Já existe: {init_path}")
        return True

def main():
    print("🔧 Criando arquivos __init__.py necessários...")
    
    # Diretórios que precisam de __init__.py
    directories = [
        'utils',
        'models', 
        'database',
        'services',
        'routes'
    ]
    
    success_count = 0
    
    for directory in directories:
        print(f"\n📁 Processando: {directory}/")
        
        # Criar diretório se não existir
        if not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
                print(f"✅ Diretório criado: {directory}/")
            except Exception as e:
                print(f"❌ Erro ao criar diretório {directory}/: {e}")
                continue
        
        # Criar __init__.py
        if create_init_file(directory):
            success_count += 1
    
    print(f"\n📊 Resultado: {success_count}/{len(directories)} arquivos __init__.py criados/verificados")
    
    if success_count == len(directories):
        print("🎉 Todos os arquivos __init__.py estão prontos!")
    else:
        print("⚠️ Alguns arquivos não puderam ser criados")

if __name__ == "__main__":
    main()
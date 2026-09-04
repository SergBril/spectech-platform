import os

print("=" * 60)
print("DIAGNOSING LOGIN ISSUE")
print("=" * 60)

# 1. Показать функцию login из симулятора
sim_path = 'scripts/gps_simulator.py'
print(f"\n📄 {sim_path} - функция login:")
print("-" * 60)
with open(sim_path, 'r', encoding='utf-8') as f:
    content = f.read()
    in_login = False
    for line in content.split('\n'):
        if 'async def login' in line:
            in_login = True
        if in_login:
            print(line)
            if line.strip() and not line.startswith(' ') and not line.startswith('\t') and 'async def login' not in line:
                break
            if 'return resp' in line or ('resp.json' in line and 'access_token' in line):
                # Показываем ещё 2 строки после return
                break

# 2. Найти endpoint логина в бэкенде
print(f"\n🔍 Ищем endpoint /auth/login в бэкенде...")
for root, dirs, files in os.walk('app'):
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    content = f.read()
                    if '/login' in content and ('@router.post' in content or '@app.post' in content):
                        print(f"\n📄 Найден в {filepath}:")
                        print("-" * 60)
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if '/login' in line and ('post' in line.lower() or i > 0 and 'post' in lines[i-1].lower()):
                                # Показываем 15 строк вокруг
                                start = max(0, i - 2)
                                end = min(len(lines), i + 15)
                                for j in range(start, end):
                                    print(f"{j+1:3d}: {lines[j]}")
                                break
                except:
                    pass

print("\n" + "=" * 60)
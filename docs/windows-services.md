# Автозапуск на Windows: recorder + SSH туннель как службы

## Почему Task Scheduler недостаточно

Триггер `AtLogOn` срабатывает только когда пользователь входит в систему.
После восстановления питания Windows стартует, но никто не логинится —
процессы не запустятся.

**Решение: Windows-службы через NSSM.**
Службы стартуют до логина, перезапускаются при падении, живут вечно.

---

## 1. Установить NSSM

```powershell
# Через winget (Windows 10/11):
winget install nssm

# Или скачать вручную: https://nssm.cc/download
# Распакуйте nssm.exe в C:\Windows\System32\ (или любую папку из PATH)
```

Проверить:
```powershell
nssm version
```

---

## 2. Служба: SSH туннель

Создайте скрипт `C:\FamilyAssistant\YACAID\tunnel.cmd`:
```bat
@echo off
:loop
ssh -N ^
    -i "%USERPROFILE%\.ssh\yacaid_tunnel" ^
    -o "ServerAliveInterval=30" ^
    -o "ServerAliveCountMax=3" ^
    -o "ExitOnForwardFailure=yes" ^
    -o "StrictHostKeyChecking=accept-new" ^
    -R 127.0.0.1:8090:127.0.0.1:8090 ^
    tunnel@VPS_IP
timeout /t 10 /nobreak
goto loop
```

> Замените `tunnel@VPS_IP` на реальные значения.

Зарегистрируйте как службу (PowerShell **от администратора**):
```powershell
nssm install "YACAID-Tunnel" "C:\Windows\System32\cmd.exe" "/c C:\FamilyAssistant\YACAID\tunnel.cmd"
nssm set "YACAID-Tunnel" DisplayName "YACAID SSH Tunnel"
nssm set "YACAID-Tunnel" Description "SSH reverse tunnel: local recorder -> VPS"
nssm set "YACAID-Tunnel" Start SERVICE_AUTO_START
nssm set "YACAID-Tunnel" AppStdout "C:\FamilyAssistant\YACAID\logs\tunnel.log"
nssm set "YACAID-Tunnel" AppStderr "C:\FamilyAssistant\YACAID\logs\tunnel.log"
nssm set "YACAID-Tunnel" AppRotateFiles 1
nssm set "YACAID-Tunnel" AppRotateBytes 10485760

New-Item -ItemType Directory -Path "C:\FamilyAssistant\YACAID\logs" -Force
nssm start "YACAID-Tunnel"
```

---

## 3. Служба: recorder (Python)

Найдите путь к Python в вашем venv:
```powershell
C:\FamilyAssistant\YACAID\.venv\Scripts\python.exe --version
```

Зарегистрируйте как службу (PowerShell **от администратора**):
```powershell
nssm install "YACAID-Recorder" "C:\FamilyAssistant\YACAID\.venv\Scripts\python.exe"
nssm set "YACAID-Recorder" AppParameters "-m recorder.app"
nssm set "YACAID-Recorder" AppDirectory "C:\FamilyAssistant\YACAID"
nssm set "YACAID-Recorder" DisplayName "YACAID Recorder"
nssm set "YACAID-Recorder" Description "YACAID camera recorder and detector"
nssm set "YACAID-Recorder" Start SERVICE_AUTO_START
nssm set "YACAID-Recorder" AppStdout "C:\FamilyAssistant\YACAID\logs\recorder.log"
nssm set "YACAID-Recorder" AppStderr "C:\FamilyAssistant\YACAID\logs\recorder.log"
nssm set "YACAID-Recorder" AppRotateFiles 1
nssm set "YACAID-Recorder" AppRotateBytes 10485760

nssm start "YACAID-Recorder"
```

Если recorder требует переменные окружения (`.env`), добавьте их:
```powershell
# Пример:
nssm set "YACAID-Recorder" AppEnvironmentExtra "RECORDER_API_TOKEN=ваш_токен"
```

---

## 4. Управление службами

```powershell
# Статус
nssm status "YACAID-Tunnel"
nssm status "YACAID-Recorder"

# Перезапуск
nssm restart "YACAID-Tunnel"
nssm restart "YACAID-Recorder"

# Остановить
nssm stop "YACAID-Tunnel"
nssm stop "YACAID-Recorder"

# Удалить службу
nssm remove "YACAID-Tunnel" confirm
nssm remove "YACAID-Recorder" confirm

# Открыть GUI для редактирования
nssm edit "YACAID-Tunnel"
```

Службы также видны в стандартном `services.msc`.

---

## 5. Проверка после перезагрузки

```powershell
Restart-Computer

# После старта проверить:
Get-Service "YACAID-Tunnel", "YACAID-Recorder"
# Ожидаемый статус: Running
```

---

## 6. Порядок зависимостей

Туннель должен стартовать после сети. Установите зависимость:
```powershell
# Туннель ждёт службу сети
nssm set "YACAID-Tunnel" DependOnService "Tcpip"

# Recorder может зависеть от туннеля (если нужен VPS при старте)
# nssm set "YACAID-Recorder" DependOnService "YACAID-Tunnel"
```

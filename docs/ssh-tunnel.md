# SSH Reverse Tunnel: recorder → VPS

## Схема

```
Локальная машина (recorder API :8090)
  │
  └─ SSH reverse tunnel ──► VPS (127.0.0.1:8090)
                                  │
                                  └─ Docker (host.docker.internal:8090)
                                            │
                                            └─ archive_server → CONTROL_BASE_URL
```

## 1. Подготовка на VPS

### Создать выделенного пользователя для туннеля (опционально, но рекомендуется)

```bash
sudo adduser --disabled-password --gecos "" tunnel
sudo -u tunnel mkdir -p /home/tunnel/.ssh
```

### Разрешить GatewayPorts для локальной петли (уже включено по умолчанию)

В `/etc/ssh/sshd_config` убедитесь что нет строки `GatewayPorts no`.
Перезапустите sshd если меняли: `sudo systemctl restart sshd`

## 2. Подготовка на локальной машине

### Сгенерировать SSH-ключ специально для туннеля

```bash
ssh-keygen -t ed25519 -C "yacaid-tunnel" -f ~/.ssh/yacaid_tunnel -N ""
```

### Скопировать публичный ключ на VPS

```bash
ssh-copy-id -i ~/.ssh/yacaid_tunnel.pub tunnel@VPS_IP
# или вручную:
cat ~/.ssh/yacaid_tunnel.pub | ssh user@VPS_IP "sudo -u tunnel tee -a /home/tunnel/.ssh/authorized_keys"
```

### Ограничить ключ только туннелями (на VPS, в /home/tunnel/.ssh/authorized_keys)

Добавьте перед ключом:
```
restrict,port-forwarding ssh-ed25519 AAAA...
```

### Проверить туннель вручную

```bash
ssh -N -i ~/.ssh/yacaid_tunnel \
    -R 127.0.0.1:8090:127.0.0.1:8090 \
    tunnel@VPS_IP
```

Если recorder отвечает на `127.0.0.1:8090`, с VPS должно работать:
```bash
curl http://127.0.0.1:8090/control/all/status
```

## 3. Автозапуск через systemd (на локальной машине)

Установите `autossh`:
```bash
# Ubuntu/Debian
sudo apt install autossh
# macOS
brew install autossh
```

Создайте файл сервиса `~/.config/systemd/user/yacaid-tunnel.service`:

```ini
[Unit]
Description=YACAID SSH reverse tunnel to VPS
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/autossh -N \
  -M 0 \
  -i %h/.ssh/yacaid_tunnel \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=accept-new \
  -R 127.0.0.1:8090:127.0.0.1:8090 \
  tunnel@VPS_IP
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

Замените `VPS_IP` и `tunnel` на ваши значения.

Включите и запустите:
```bash
systemctl --user daemon-reload
systemctl --user enable yacaid-tunnel
systemctl --user start yacaid-tunnel
systemctl --user status yacaid-tunnel
```

Чтобы сервис жил без активной сессии пользователя:
```bash
sudo loginctl enable-linger $USER
```

## 4. Настройка на VPS

В файле `.env` (в корне проекта):

```env
CONTROL_BASE_URL=http://host.docker.internal:8090
CONTROL_API_TOKEN=ваш_токен
```

Перезапустить:
```bash
docker compose up -d
```

## macOS: альтернатива — LaunchAgent

Создайте `~/Library/LaunchAgents/com.yacaid.tunnel.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.yacaid.tunnel</string>
  <key>ProgramArguments</key>
  <array>
    <string>/opt/homebrew/bin/autossh</string>
    <string>-N</string>
    <string>-M</string><string>0</string>
    <string>-i</string><string>/Users/YOU/.ssh/yacaid_tunnel</string>
    <string>-o</string><string>ServerAliveInterval=30</string>
    <string>-o</string><string>ServerAliveCountMax=3</string>
    <string>-o</string><string>ExitOnForwardFailure=yes</string>
    <string>-R</string><string>127.0.0.1:8090:127.0.0.1:8090</string>
    <string>tunnel@VPS_IP</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/com.yacaid.tunnel.plist
```

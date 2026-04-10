# Виртуальное окружение

Папка проекта синхронизируется через Яндекс.Диск и Git, поэтому виртуальное окружение Python лучше хранить вне репозитория. На каждом компьютере должно быть свое локальное окружение.

## Windows PowerShell

```powershell
py -0p
py -3.13 -m venv $HOME\.venvs\eve_craft
$HOME\.venvs\eve_craft\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## macOS / Linux

```bash
python3.13 --version
python3.13 -m venv ~/.venvs/eve_craft
source ~/.venvs/eve_craft/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Если окружение сломалось

Если проект был перенесен в другую папку, открыт на другом компьютере или после обновления Python появились проблемы, удалите только локальное виртуальное окружение и создайте его заново на текущем устройстве.

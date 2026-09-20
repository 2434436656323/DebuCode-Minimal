# DebuCode Minimal v0.2

Минималистичный язык программирования, похожий на Python.

## Запуск

```bash
python debucode.py файл.dcm
```

## Синтаксис

Похож на Python. Поддерживаются:
- `true` / `false` / `None` (а также `True` / `False`)
- Двоеточия после `if`, `while`, `for`, `def` (опциональны)
- Именованные аргументы: `func(name=value)`
- Значения по умолчанию в функциях: `def f(x, y=10):`

## Встроенные модули

Все модули доступны через `import`:

| Модуль | Описание |
|--------|----------|
| `random` | randint, choice, shuffle, random, uniform, randrange, seed, sample |
| `os` | getcwd, listdir, mkdir, remove, rename, path, environ, system, _exit |
| `sys` | argv, exit, stdout, stderr, stdin, path, platform, version |
| `subprocess` | run, Popen, call, check_call, check_output, PIPE, STDOUT |
| `tkinter` | Полный модуль tkinter (GUI) |
| `flask` | Flask, request, jsonify, redirect, render_template_string |
| `math` | pi, e, sqrt, sin, cos, tan, log, floor, ceil, pow, factorial |
| `time` | time, sleep, ctime, localtime, strftime |
| `json` | dumps, loads, load, dump |

## Импорт

```debucode
# Встроенные модули
import random
import os
import flask
from random import randint, choice
from flask import Flask, jsonify

# Внешние ZIP-пакеты
import mymath
```

## Внешние пакеты (ZIP)

Создайте ZIP-архив `mymath.zip` со структурой:
```
mymath.zip
├── init.dcm      → start: main.dcm / files: utils.dcm
├── main.dcm
└── utils.dcm
```

`init.dcm` — конфиг пакета:
```
start: main.dcm
files: utils.dcm
```

## Примеры

### Базовая программа
```debucode
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

for i in range(10):
    print(fib(i))
```

### Flask API
```debucode
import flask

app = flask.Flask("myapi")

def hello():
    return flask.jsonify({"msg": "Hi!"})

app.add_url_rule("/hello", "hello", hello)
app.run(host="0.0.0.0", port=5000, debug=true)
```

### random
```debucode
import random
print(random.randint(1, 100))
print(random.choice(["a", "b", "c"]))
```

### subprocess
```debucode
import subprocess
r = subprocess.run(["echo", "hi"], capture_output=true, text=true)
print(r.stdout)
```

## Стандартные функции

print, len, range, str, int, float, bool, list, dict, abs, min, max, sum,
sorted, reversed, enumerate, zip, map, filter, type, isinstance, round,
open, input, tuple, set, any, all, chr, ord, hex, bin, oct, repr, format

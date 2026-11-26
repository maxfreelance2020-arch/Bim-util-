"""Локальная проверка шести решений. В CATS этот файл отправлять не нужно.

Только стандартная библиотека Python 3. Тесты сами создают BMP, включая
верхний порядок строк, расширенные заголовки и ненулевое выравнивание.
"""

import argparse
import json
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
TASKS = {
    "info": "I1A_info",
    "copy": "I1B_copy",
    "invert": "I2A_invert",
    "gray": "I2B_gray",
    "bright": "I2C_bright",
    "threshold": "I2D_threshold",
}
COLORS = [
    (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
    (0, 0, 255), (255, 255, 0), (200, 100, 50), (250, 128, 3),
    (127, 127, 127), (128, 128, 128), (10, 13, 26), (1, 254, 255),
]


def make_bmp(width, height, *, top_down=False, dib_size=40, gap=b"",
             tail=b"", zero_image_size=False, seed=1, repeated=False):
    """Создать 24-битный BMP; цвета задаём как RGB, в файл пишем BGR."""
    rng = random.Random(seed)
    stride = (width * 3 + 3) // 4 * 4
    rows = []
    for y in range(1 if repeated else height):
        row = bytearray()
        for x in range(width):
            if x + y * width < len(COLORS):
                red, green, blue = COLORS[x + y * width]
            else:
                red, green, blue = (rng.randrange(256) for _ in range(3))
            row.extend((blue, green, red))
        # Ненулевые байты: тест заметит, если программа обработает их как цвет.
        row.extend(bytes((0xA5 + y % 10,)) * (stride - width * 3))
        rows.append(bytes(row))
    pixels = rows[0] * height if repeated else b"".join(rows)
    offset = 14 + dib_size + len(gap)
    dib = bytearray(dib_size)
    struct.pack_into("<IiiHHIIiiII", dib, 0, dib_size, width,
                     -height if top_down else height, 1, 24, 0,
                     0 if zero_image_size else len(pixels), 2835, 2835, 0, 0)
    if dib_size >= 108:
        struct.pack_into("<I", dib, 56, 0x73524742)  # LCS_sRGB.
    if dib_size >= 124:
        struct.pack_into("<I", dib, 108, 4)  # LCS_GM_IMAGES.
    header = struct.pack("<2sIHHI", b"BM", offset + len(pixels) + len(tail),
                         0, 0, offset)
    return header + dib + gap + pixels + tail


def dimensions(bmp):
    width, signed_height = struct.unpack_from("<ii", bmp, 18)
    return width, abs(signed_height)


def make_demo_bmp():
    """Понятный визуальный пример: цветные полосы и плавный переход цветов."""
    width, height = 256, 128
    bmp = bytearray(make_bmp(width, height))
    bars = COLORS[:8]
    for y in range(height):
        for x in range(width):
            if y >= height // 2:
                red, green, blue = bars[x // 32]
            else:
                red, green, blue = x, y * 4, 255 - x
            position = 54 + (y * width + x) * 3
            bmp[position:position + 3] = bytes((blue, green, red))
    return bytes(bmp)


def check_result(original, result, command, parameter=None, *, repeated=False):
    """Проверяем требования задачи и сохранность всех служебных байтов."""
    if command == "copy":
        assert result == original, "copy: файлы различаются побайтово"
        return

    width, height = dimensions(original)
    assert len(result) == len(original), "Изменилась длина BMP"
    assert dimensions(result) == (width, height), "Изменились размеры"
    offset = struct.unpack_from("<I", original, 10)[0]
    stride = (width * 3 + 3) // 4 * 4
    end = offset + stride * height
    assert result[:offset] == original[:offset], "Изменился заголовок/зазор"
    assert result[end:] == original[end:], "Изменились данные после пикселей"
    rows_to_check = height
    if repeated:
        first_row = result[offset:offset + stride]
        assert result[offset:end] == first_row * height, "Строки различаются"
        rows_to_check = 1

    for y in range(rows_to_check):
        start = offset + y * stride
        assert result[start + width * 3:start + stride] == \
            original[start + width * 3:start + stride], "Изменилось выравнивание"
        for x in range(width):
            pos = start + x * 3
            old = original[pos:pos + 3]
            new = result[pos:pos + 3]
            blue, green, red = old
            luminance = 0.299 * red + 0.587 * green + 0.114 * blue
            if command == "invert":
                assert tuple(new) == tuple(255 - value for value in old)
            elif command == "bright":
                expected = tuple(max(0, min(255, value + parameter)) for value in old)
                assert tuple(new) == expected
            elif command == "gray":
                assert new[0] == new[1] == new[2], "Пиксель не серый"
                assert abs(new[0] - luminance) <= 1.000000001, "Неверная яркость"
            elif command == "threshold":
                assert new in (b"\x00\x00\x00", b"\xff\xff\xff")
                if abs(luminance - parameter) > 1.000000001:
                    assert (new[0] == 255) == (luminance >= parameter)


def find_compiler(explicit):
    if explicit:
        return str(Path(explicit).resolve())
    available = shutil.which("gcc") or shutil.which("clang")
    if available:
        return available
    jetbrains = Path("C:/Program Files/JetBrains")
    candidates = sorted(jetbrains.glob("CLion */bin/mingw/bin/gcc.exe"))
    if candidates:
        return str(candidates[-1])
    raise SystemExit("Компилятор не найден. Укажите: --compiler ПУТЬ_К_GCC")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", help="Путь к gcc или clang")
    parser.add_argument("--bin-dir", type=Path,
                        help="Папка программ, уже собранных CMake; повторно не компилировать")
    parser.add_argument("--work-dir", type=Path, help="Папка временных файлов проверок")
    parser.add_argument("--report", type=Path, help="Путь к JSON-отчёту")
    parser.add_argument("--time-limit", type=float, default=0,
                        help="Необязательный лимит времени большого теста в секундах")
    args = parser.parse_args()
    if args.time_limit < 0:
        parser.error("--time-limit должен быть неотрицательным")
    work = args.work_dir.resolve() if args.work_dir else BUILD / "test files"
    report_path = args.report.resolve() if args.report else BUILD / "test_report.json"
    work.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    compiler = args.compiler if args.bin_dir else find_compiler(args.compiler)
    environment = os.environ.copy()
    if compiler:
        environment["PATH"] = str(Path(compiler).parent) + os.pathsep + environment.get("PATH", "")
    suffix = ".exe" if os.name == "nt" else ""
    programs = {}
    for command, task in TASKS.items():
        executable = (args.bin_dir.resolve() if args.bin_dir else BUILD) / (task + suffix)
        if not args.bin_dir:
            compile_result = subprocess.run(
                [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic",
                 "-Werror", str(ROOT / "solutions" / (task + ".c")), "-o", str(executable)],
                capture_output=True, env=environment, timeout=60,
            )
            if compile_result.returncode:
                raise AssertionError(compile_result.stderr.decode(errors="replace"))
        if not executable.is_file():
            raise AssertionError(f"Программа не найдена: {executable}. Сначала соберите проект.")
        programs[command] = executable
    if args.bin_dir:
        print("PROGRAMS: using all 6 executables built by CMake", flush=True)
    else:
        print("COMPILE: 6/6, warnings treated as errors", flush=True)

    counts = {command: 0 for command in TASKS}

    def run(command, bmp, parameter=None, *, cli=False, repeated=False):
        text = command if parameter is None else f"{command} {parameter}"
        for name in ("output.txt", "output.bmp", "result image.bmp"):
            path = work / name
            if path.exists():
                path.unlink()  # Удаляем только известный выходной файл теста.
        if cli:
            source = work / "source image.bmp"
            source.write_bytes(bmp)
            arguments = [str(programs[command]), command]
            if parameter is not None:
                arguments.append(str(parameter))
            arguments.append(str(source))
            if command != "info":
                arguments.append(str(work / "result image.bmp"))
        else:
            (work / "input.bin").write_bytes(text.encode("ascii") + b"\n" + bmp)
            arguments = [str(programs[command])]
        start = time.perf_counter()
        process = subprocess.run(arguments, cwd=work, env=environment,
                                 capture_output=True, timeout=max(30, args.time_limit))
        duration = time.perf_counter() - start
        assert process.returncode == 0, f"{text}: код завершения {process.returncode}"
        assert not process.stderr, f"{text}: неожиданный stderr"
        if command == "info":
            actual = process.stdout if cli else (work / "output.txt").read_bytes()
            width, height = dimensions(bmp)
            assert actual == f"{width} {height}".encode("ascii"), "Неверный info"
        else:
            assert not process.stdout, "Лишний текст в стандартном выводе"
            path = work / ("result image.bmp" if cli else "output.bmp")
            actual = path.read_bytes()
            check_result(bmp, actual, command, parameter, repeated=repeated)
        if not cli:
            assert not process.stdout, "Лишний текст в режиме CATS"
        counts[command] += 1
        return actual, duration

    fixtures = [make_bmp(width, 3, seed=width) for width in range(1, 10)]
    fixtures.extend([
        make_bmp(1, 1),
        make_bmp(1, 1, top_down=True),
        make_bmp(5, 4, top_down=True, zero_image_size=True),
        make_bmp(7, 2, dib_size=108, gap=b"\x0a\x0d\x1a\xff\x00"),
        make_bmp(11, 5, dib_size=124, top_down=True, gap=b"metadata" * 7),
        make_bmp(17, 9, tail=b"extra\x00\x0a\x0d\x1a\xff", seed=77),
        make_bmp(305, 183, top_down=True, seed=305),
    ])
    for bmp in fixtures:
        for command in ("info", "copy", "invert", "gray"):
            run(command, bmp)
        for change in (-255, -254, -10, 0, 10, 254, 255):
            run("bright", bmp, change)
        for threshold in (0, 1, 76, 127, 128, 254, 255):
            run("threshold", bmp, threshold)
    print("CATS: padding 0/1/2/3, negative height, V4/V5, extra fields, boundary parameters OK",
          flush=True)

    cli_fixture = make_bmp(7, 5, top_down=True, dib_size=124, gap=b"gap")
    for command in ("info", "copy", "invert", "gray"):
        run(command, cli_fixture, cli=True)
    for command, values in (("bright", (-255, 0, 10, 255)),
                            ("threshold", (0, 128, 255))):
        for parameter in values:
            run(command, cli_fixture, parameter, cli=True)
    print("CLI: all six commands, paths containing spaces and Cyrillic OK", flush=True)

    # Свойства помогают поймать ошибки, которые не видны на одном примере.
    for bmp in fixtures[:9]:
        inverted, _ = run("invert", bmp)
        restored, _ = run("invert", inverted)
        assert restored == bmp, "Два негатива должны восстановить исходный файл"
        unchanged, _ = run("bright", bmp, 0)
        assert unchanged == bmp, "bright 0 должен сохранить файл побайтово"
    print("PROPERTIES: double inversion and bright 0 OK", flush=True)

    # Проверяем примеры из присланных условий явно, включая границы 0/255.
    example = make_bmp(12, 1)
    inverted, _ = run("invert", example)
    assert tuple(reversed(inverted[54 + 6 * 3:54 + 7 * 3])) == (55, 155, 205)
    brighter, _ = run("bright", example, 10)
    assert tuple(reversed(brighter[54 + 7 * 3:54 + 8 * 3])) == (255, 138, 13)
    darker, _ = run("bright", example, -10)
    assert tuple(reversed(darker[54 + 7 * 3:54 + 8 * 3])) == (240, 118, 0)
    black_white, _ = run("threshold", example, 128)
    assert black_white[54 + 2 * 3:54 + 3 * 3] == b"\x00\x00\x00"
    assert black_white[54 + 5 * 3:54 + 6 * 3] == b"\xff\xff\xff"

    invalid_count = 0
    for command, contents in (
        ("info", b"info\nBM"), ("copy", b""),
        ("invert", b"invert\n" + example[:-1]),
        ("gray", b"gray\nBM"),
        ("bright", b"bright 256\n" + example),
        ("bright", b"bright -256\n" + example),
        ("threshold", b"threshold -1\n" + example),
        ("threshold", b"threshold 256\n" + example),
    ):
        (work / "input.bin").write_bytes(contents)
        result = subprocess.run([str(programs[command])], cwd=work,
                                env=environment, capture_output=True, timeout=10)
        assert result.returncode != 0, "Повреждённый вход должен завершаться с ошибкой"
        invalid_count += 1
    print(f"ERROR HANDLING: {invalid_count} checks OK", flush=True)

    large = make_bmp(2000, 2000, top_down=True, repeated=True, seed=2026)
    timings = {}
    for command in TASKS:
        parameter = 10 if command == "bright" else 128 if command == "threshold" else None
        _, duration = run(command, large, parameter, repeated=True)
        timings[command] = round(duration, 4)
        if args.time_limit:
            assert duration < args.time_limit, f"{command}: локальный запуск занял {duration:.3f} с"
    print("LARGE 2000x2000, seconds: " + json.dumps(timings), flush=True)

    # Сохраняем примеры для просмотра и самостоятельных экспериментов.
    demo_dir = report_path.parent / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    demo = make_demo_bmp()
    (demo_dir / "original.bmp").write_bytes(demo)
    for command in TASKS:
        parameter = 40 if command == "bright" else 128 if command == "threshold" else None
        result, _ = run(command, demo, parameter, cli=True)
        name = "info.txt" if command == "info" else command + ".bmp"
        (demo_dir / name).write_bytes(result)
    print("DEMO: original.bmp and all six results saved", flush=True)

    report = {
        "compiler": compiler,
        "checks_by_command": counts,
        "valid_checks": sum(counts.values()),
        "invalid_checks": invalid_count,
        "total_checks": sum(counts.values()) + invalid_count,
        "large_image_seconds": timings,
        "time_limit_seconds": args.time_limit or None,
        "status": "PASS",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS: " + json.dumps(counts) + f"; total valid checks = {sum(counts.values())}",
          flush=True)
    print("Report: " + str(report_path), flush=True)
    print("Demo: " + str(demo_dir), flush=True)


if __name__ == "__main__":
    main()

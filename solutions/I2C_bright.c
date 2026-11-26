#include <stdio.h>
#include <string.h>

/* Четырёхбайтовое число BMP хранится младшим байтом вперёд.
   LL задаёт тип long long, чтобы промежуточные значения не переполнили int. */
long long read_number(const unsigned char bytes[], int start)
{
    return bytes[start]
         + bytes[start + 1] * 256LL
         + bytes[start + 2] * 65536LL
         + bytes[start + 3] * 16777216LL;
}

/* Копируем оставшуюся часть файла без изменений. */
int copy_remaining(FILE *input, FILE *output)
{
    unsigned char buffer[4096];
    size_t count; /* size_t — тип, которым fread сообщает число прочитанных байтов. */

    /* fread возвращает число реально прочитанных байтов.
       На последнем шаге их может быть меньше размера массива. */
    while ((count = fread(buffer, 1, sizeof(buffer), input)) > 0) {
        if (fwrite(buffer, 1, count, output) != count) {
            return 1; /* Не удалось записать всю порцию. */
        }
    }

    if (ferror(input)) {
        return 1; /* Чтение остановилось из-за ошибки, а не конца файла. */
    }

    return 0;
}

int process_image(FILE *input, FILE *output, int change)
{
    /* 54 = 14 байтов заголовка файла + первые 40 байтов описания картинки.
       Сам заголовок может быть длиннее: всё до пикселей скопируем отдельно. */
    unsigned char header[54];

    /* Максимальная ширина — 2000 пикселей.
       Строка вместе с выравниванием занимает не больше 6000 байтов. */
    unsigned char row[6000];

    if (fread(header, 1, sizeof(header), input) != sizeof(header)) {
        return 1;
    }

    /* BM — подпись BMP; 24 — число бит на пиксель; 0 — отсутствие сжатия. */
    if (header[0] != 'B' || header[1] != 'M'
        || read_number(header, 14) < 40
        || header[26] != 1 || header[27] != 0
        || header[28] != 24 || header[29] != 0
        || read_number(header, 30) != 0) {
        return 1;
    }

    /* Все позиции считаются от начала BMP, после строки команды. */
    long long pixel_offset = read_number(header, 10);
    long long width_value = read_number(header, 18);
    long long height_value = read_number(header, 22);

    /* В заголовке высота бывает отрицательной.
       При чтении как беззнакового числа -h выглядит как 2^32 - h.
       Поэтому 4294967296 - прочитанное число даёт положительную высоту.
       2147483648 = 2^31, 4294967296 = 2^32. */
    if (height_value >= 2147483648LL) {
        height_value = 4294967296LL - height_value;
    }

    /* Проверяем ограничения перед преобразованием long long в int. */
    if (width_value < 1 || width_value > 2000
        || height_value < 1 || height_value > 2000
        || pixel_offset < 54) {
        return 1;
    }

    int width = (int)width_value;
    int height = (int)height_value;

    /* На пиксель нужно 3 байта. Длину строки округляем вверх до кратной 4.
       Например: ширина 3 -> 9 байтов цветов + 3 байта выравнивания = 12. */
    int row_size = (width * 3 + 3) / 4 * 4;

    /* Размеры и формат не меняются, поэтому сохраняем исходный заголовок. */
    if (fwrite(header, 1, sizeof(header), output) != sizeof(header)) {
        return 1;
    }

    /* До пикселей могут находиться дополнительные поля.
       Начало пикселей берём из заголовка, а не считаем всегда равным 54. */
    for (long long position = 54; position < pixel_offset; position++) {
        int byte = fgetc(input);
        if (byte == EOF || fputc(byte, output) == EOF) {
            return 1;
        }
    }

    /* Читаем и записываем по одной строке, поэтому вся картинка
       одновременно в памяти не нужна. Порядок строк сохраняем. */
    for (int y = 0; y < height; y++) {
        if (fread(row, 1, (size_t)row_size, input) != (size_t)row_size) {
            return 1;
        }

        for (int x = 0; x < width; x++) {
            /* Каждый пиксель занимает три соседних элемента массива. */
            int position = x * 3;

            /* Прибавляем change отдельно к B, G и R.
               int нужен, чтобы временно получить отрицательное число
               или число больше 255, а затем правильно ограничить его. */
            for (int channel = 0; channel < 3; channel++) {
                int value = row[position + channel] + change;

                if (value < 0) {
                    value = 0;
                }
                if (value > 255) {
                    value = 255;
                }

                /* После ограничения число точно помещается в один байт. */
                row[position + channel] = (unsigned char)value;
            }
        }

        /* Записываем всю строку, включая неизменённые байты выравнивания. */
        if (fwrite(row, 1, (size_t)row_size, output) != (size_t)row_size) {
            return 1;
        }
    }

    /* Если после пикселей есть дополнительные данные, тоже сохраняем их. */
    return copy_remaining(input, output);
}

/* Без аргументов читаем input.bin, иначе используем пути из argv. */
int main(int argc, char *argv[])
{
    FILE *input;
    FILE *output;
    char command_line[64]; /* Первая строка input.bin. */
    int change; /* Изменение яркости от -255 до 255. */

    if (argc == 1) {
        /* rb — чтение в двоичном режиме: байты BMP не преобразуются. */
        input = fopen("input.bin", "rb");
        if (input == NULL) {
            return 1;
        }

        /* fgets забирает строку команды вместе с LF.
           После этого следующими будут ровно байты BMP. */
        if (fgets(command_line, sizeof(command_line), input) == NULL) {
            fclose(input);
            return 1;
        }

        /* %31s читает имя команды, %d — целый параметр.
           &change передаёт адрес переменной, куда записать число. */
        char command_name[32];
        if (sscanf(command_line, "%31s %d", command_name, &change) != 2
            || strcmp(command_name, "bright") != 0
            || change < -255 || change > 255) {
            fclose(input);
            return 1;
        }

        output = fopen("output.bmp", "wb");
    } else {

        if (argc != 5 || strcmp(argv[1], "bright") != 0) {
            return 1;
        }

        if (sscanf(argv[2], "%d", &change) != 1
            || change < -255 || change > 255) {
            return 1;
        }

        /* При совпадении путей открытие на запись очистило бы исходный файл. */
        if (strcmp(argv[3], argv[4]) == 0) {
            return 1;
        }

        input = fopen(argv[3], "rb");
        if (input == NULL) {
            return 1;
        }

        output = fopen(argv[4], "wb");
    }

    if (output == NULL) {
        fclose(input);
        return 1;
    }

    int result = process_image(input, output, change);

    /* Ошибка отложенной записи может проявиться при закрытии файла. */
    if (fclose(input) != 0) {
        result = 1;
    }
    if (fclose(output) != 0) {
        result = 1;
    }

    return result; /* 0 — успешное завершение программы, 1 — ошибка. */
}

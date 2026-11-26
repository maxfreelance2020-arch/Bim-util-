#include <stdio.h>
#include <string.h>

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

/* Без аргументов читаем input.bin, иначе используем пути из argv. */
int main(int argc, char *argv[])
{
    FILE *input;
    FILE *output;
    char command_line[64]; /* Первая строка input.bin. */

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

        output = fopen("output.bmp", "wb");
    } else {

        if (argc != 4 || strcmp(argv[1], "copy") != 0) {
            return 1;
        }

        /* При совпадении путей открытие на запись очистило бы исходный файл. */
        if (strcmp(argv[2], argv[3]) == 0) {
            return 1;
        }

        input = fopen(argv[2], "rb");
        if (input == NULL) {
            return 1;
        }

        output = fopen(argv[3], "wb");
    }

    if (output == NULL) {
        fclose(input);
        return 1;
    }

    int result = copy_remaining(input, output);

    /* Ошибка отложенной записи может проявиться при закрытии файла. */
    if (fclose(input) != 0) {
        result = 1;
    }
    if (fclose(output) != 0) {
        result = 1;
    }

    return result; /* 0 — успешное завершение программы, 1 — ошибка. */
}

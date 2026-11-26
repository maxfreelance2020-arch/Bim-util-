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

/* Печатаем только ширину и положительную высоту через пробел. */
int print_info(FILE *input, FILE *output)
{
    unsigned char header[54];

    if (fread(header, 1, sizeof(header), input) != sizeof(header)) {
        return 1;
    }

    if (header[0] != 'B' || header[1] != 'M') {
        return 1;
    }

    /* 18 — позиция ширины, 22 — позиция высоты в заголовке BMP.
       Каждое из этих полей занимает 4 байта. */
    long long width_value = read_number(header, 18);
    long long height_value = read_number(header, 22);

    /* В заголовке высота бывает отрицательной.
       При чтении как беззнакового числа -h выглядит как 2^32 - h.
       Поэтому 4294967296 - прочитанное число даёт положительную высоту.
       2147483648 = 2^31, 4294967296 = 2^32. */
    if (height_value >= 2147483648LL) {
        height_value = 4294967296LL - height_value;
    }

    if (width_value < 1 || width_value > 2000
        || height_value < 1 || height_value > 2000) {
        return 1;
    }

    int width = (int)width_value;
    int height = (int)height_value;

    if (fprintf(output, "%d %d", width, height) < 0) {
        return 1;
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

        output = fopen("output.txt", "w");
    } else {

        if (argc != 3 || strcmp(argv[1], "info") != 0) {
            return 1;
        }

        input = fopen(argv[2], "rb");
        if (input == NULL) {
            return 1;
        }

        /* stdout — стандартный вывод: размеры появятся в терминале. */
        output = stdout;
    }

    if (output == NULL) {
        fclose(input);
        return 1;
    }

    int result = print_info(input, output);

    /* Ошибка отложенной записи может проявиться при закрытии файла. */
    if (fclose(input) != 0) {
        result = 1;
    }
    if (fclose(output) != 0) {
        result = 1;
    }

    return result; /* 0 — успешное завершение программы, 1 — ошибка. */
}

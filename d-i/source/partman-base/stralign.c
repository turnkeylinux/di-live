#include <stdio.h>
#include <locale.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

int
main(int argc, char **argv)
{
        int space;
        int length;
        int width;
        wchar_t *string;
        setlocale(LC_ALL, "");
        sscanf(argv[1], "%i", &space);
        length = strlen(argv[2]);
        string = (wchar_t *) malloc(sizeof(wchar_t[length]));
        mbstowcs(string, argv[2], length + 2);
        width = wcswidth(string, length + 2);
        if (space > 0 && space > width) {
                int i;
                for (i = width; i < space; i++)
                        putchar(' ');
        }
        printf("%s", argv[2]);
        if (space < 0 && -space > width) {
                int i;
                for (i = width; i < -space; i++)
                        putchar(' ');
        }
        return 0;
}


/*
Local variables:
indent-tabs-mode: nil
c-file-style: "linux"
c-font-lock-extra-types: ("FILE" "\\sw+_t" "bool" "Ped\\sw+")
End:
*/

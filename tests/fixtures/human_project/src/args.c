/* arg parsing, quick and dirty */
#include <stdio.h>

int main(int argc, char **argv)
{
	int i;
	for (i = 1; i < argc; i++) {
		if (argv[i][0] == '-')
			continue;
		puts(argv[i]);
	}
	return 0;
}

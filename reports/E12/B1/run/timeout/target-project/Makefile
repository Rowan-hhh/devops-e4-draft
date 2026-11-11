CFLAGS = -O0

.PHONY: all clean test
all: app
app: main.o helper.o
	gcc main.o helper.o -o app
main.o: main.c config.h
	gcc $(CFLAGS) -c main.c -o main.o
helper.o: helper.c
	gcc $(CFLAGS) -c helper.c -o helper.o
test: app
	./app
clean:
	rm -f app main.o helper.o hello

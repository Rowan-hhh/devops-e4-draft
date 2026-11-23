CFLAGS = -O0
HELPER_DEPS = helper.c scale.h

.PHONY: all clean test
all: app
app: main.o helper.o
	gcc main.o helper.o -o app
main.o: main.c config.h
	gcc $(CFLAGS) -c main.c -o main.o
helper.o: $(HELPER_DEPS)
	gcc $(CFLAGS) -c helper.c -o helper.o
test: app
	./app | grep -qx 1
clean:
	rm -f app main.o helper.o

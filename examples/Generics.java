class Pair<T, U> {

    T first;
    U second;

    Pair(T first, U second) {
        this.update(first, second);
    }

    static void main() {
        {
            int a = (1 > 3) ? 1 : 2;
            System.out.println(Integer.toString(a));
        }

        System.out.println("User-made generic type.");
        Pair<int, String> test = new Pair<int, String>(1, "Test");
        Pair<Pair<int, String>, String> test2 =
            new Pair<Pair<int, String>, String>(test, "Yeah");
        System.out.println(Integer.toString(test2.getFirst().getFirst()));
        System.out.println(test2.getFirst().getSecond());
        System.out.println(test2.getSecond());
        System.out.println(Integer.toString(Pair.test(1)));
    }

    static <T> T test(T test) {
        return test;
    }

    T getFirst() {
        return this.first;
    }

    void setFirst(T first) {
       this.first = first;
    }

    U getSecond() {
        return this.second;
    }

    void setSecond(U second) {
        this.second = second;
    }

    void update(T first, U second) {
        this.first = first;
        this.second = second;
    }

}

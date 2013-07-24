class Test {

    Test() {
    }

    static void main() {
        int a = 1 + 2 * 3;
        int d = 1 * 3 + 2;
        int b = (1 + 2) * 3;
        int c = 1 % 3 * (2 + 4) * 3 - 2;

        boolean test = 1 < 3 * 2;

        System.out.println(Integer.toString(a));
        System.out.println(Integer.toString(b));
        System.out.println(Integer.toString(c));
        System.out.println(test ? "YES" : "NO");
    }

}

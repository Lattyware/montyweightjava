import java.util.List;

class Test {

    Test(String test) {
        System.out.println(test);
    }

    void only_in_test() {
        System.out.println("In Test");
    }

    void in_both() {
        System.out.println("In Test");
    }

    static void static_in_test() {
        System.out.println("In Test");
    }

}

class Test2 extends Test {

    Test2() {
        super("TEST");
    }

    static void main() {
        Test2 test = new Test2();
        test.only_in_test();
        test.in_both();
        test.only_in_test2();
        Test2.static_in_test();
        Test.static_in_test();

        TestList<Object> cast_test = (TestList<Object>) new TestList<String>();

        TestList<String> list = new TestList<String>();
        list.add("Test");
        System.out.println(list.get(0));
    }

    void in_both() {
        System.out.println("In Test2");
    }

    void only_in_test2() {
        System.out.println("In Test2");
    }

}

class TestList<F> extends List<F> {

    TestList() {
    }

}

import java.util.List;

class MergeSorter {

    MergeSorter() {
    }

    static void main() {
        List<int> list = new List<int>();
        list.add(1);
        list.add(6);
        list.add(2);
        list.add(3);
        list.add(100);
        list.add(-10);
        list.add(0);

        List<int> ascending = MergeSorter.sort(list, true);
        List<int> descending = MergeSorter.sort(list, false);

        System.out.println("Merge sort of:");
        MergeSorter.print_list(list);
        System.out.println("\nAscending:");
        MergeSorter.print_list(ascending);
        System.out.println("\nDescending:");
        MergeSorter.print_list(descending);
    }

    static void print_list(List<int> list) {
        for (int i = 0; i < list.size(); i++) {
            System.out.println(Integer.toString(list.get(i)));
        }
    }

    static <T> List<T> sort(List<T> list, boolean ascending) {
        if (list.size() <= 1) {
            return list;
        }
        List<T> left = new List<T>();
        List<T> right = new List<T>();
        int middle = list.size() / 2;
        for (int i = 0; i < middle; i++) {
            left.add(list.get(i));
        }
        for (int i = middle; i < list.size(); i++) {
            right.add(list.get(i));
        }
        left = MergeSorter.sort(left, ascending);
        right = MergeSorter.sort(right, ascending);
        return MergeSorter.merge(left, right, ascending);
    }

    static <T> List<T> merge(List<T> left, List<T> right, boolean ascending) {
        List<T> result = new List<T>();
        while (left.size() > 0 || right.size() > 0) {
            List<T> target;
            if (left.size() > 0 && right.size() > 0) {
                if (left.get(0) <= right.get(0) == ascending) {
                    target = left;
                } else {
                    target = right;
                }
            } else if (left.size() > 0) {
                target = left;
            } else {
                target = right;
            }
            result.add(target.get(0));
            target.remove(0);
        }
        return result;
    }

}

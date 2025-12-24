def iterDemo(itema):
    #生成迭代器
    itema = iter([1, 2, 3])
    while True:
        try:
            #迭代器的下一个值， 如果没有更多值，返回"0"
            val = next(itema, "0")# get next item, if no more, return "0"
            print(val)
            if val == "0":
                # print("no more item")
                break
        except StopIteration:
            print("no more item")
            break

if __name__ == '__main__':
    iterDemo([1,2,3])



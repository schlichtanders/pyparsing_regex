def deleteallbutone(elm, l):
    one = False
    for i in l:
        if i == elm and not one:
            one = True
            yield i
        elif i == elm:
            continue #pass
        else:
            yield i
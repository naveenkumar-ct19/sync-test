friends = ['john', 'pat', 'gary', 'michael']

print(f"{'Iteration':<10} | {'Name':<10}")
print("-" * 25)

for i, name in enumerate(friends, start=1):
    print(f"{i:<10} | {name.capitalize():<10}")

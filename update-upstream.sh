current_branch=`git symbolic-ref --short HEAD`

git remote add upstream https://github.com/domokit/mojo
git fetch upstream
git checkout -b upstream-master --track upstream/master
git checkout upstream-master
git subtree split --prefix mojo/public/tools/bindings -b upstream-bindings
git checkout $current_branch
git subtree merge --prefix bindings upstream-bindings

current_branch=`git symbolic-ref --short HEAD`

git remote add upstream https://github.com/domokit/mojo
git fetch upstream
git checkout -b upstream-master --track upstream/master
git checkout upstream-master
git pull
git subtree split --prefix mojo/public/tools/bindings -b upstream-bindings
git subtree split --prefix mojo/public/python -b upstream-python
git checkout $current_branch
git subtree merge -m "merge upstream" --prefix lib/tools/bindings upstream-bindings
git subtree merge -m "merge upstream" --prefix lib/python upstream-python

# The following downloads require depot_tools.
download_from_google_storage.py \
   --no_resume \
   --quiet \
   --no_auth \
   --bucket mojo/mojom_parser/linux64 \
   -s lib/tools/bindings/mojom_parser/bin/linux64/mojom_parser.sha1

download_from_google_storage.py \
   --no_resume \
   --quiet \
   --no_auth \
   --bucket mojo/mojom_parser/mac64 \
   -s lib/tools/bindings/mojom_parser/bin/mac64/mojom_parser.sha1


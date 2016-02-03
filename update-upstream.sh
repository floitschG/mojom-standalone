current_branch=`git symbolic-ref --short HEAD`

git remote add upstream https://github.com/domokit/mojo
git fetch upstream
git checkout -b upstream-master --track upstream/master
git checkout upstream-master
git subtree split --prefix mojo/public/tools/bindings -b upstream-bindings
git checkout $current_branch
git subtree merge --prefix bindings upstream-bindings

# The following downloads require depot_tools.
download_from_google_storage.py \
   --no_resume \
   --quiet \
   --no_auth \
   --bucket mojo/mojom_parser/linux64 \
   -s bindings/mojom_parser/bin/linux64/mojom_parser.sha1

download_from_google_storage.py \
   --no_resume \
   --quiet \
   --no_auth \
   --bucket mojo/mojom_parser/mac64 \
   -s bindings/mojom_parser/bin/mac64/mojom_parser.sha1


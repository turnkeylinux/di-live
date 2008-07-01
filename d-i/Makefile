unexport DH_OPTIONS

SOURCEDIR := source

build:
	for package in $(SOURCEDIR)/*; do \
		(cd $$package && debian/rules build) || exit 1; \
	done

install:
	for package in $(SOURCEDIR)/*; do \
		(cd $$package && debian/rules binary && rm -rf debian/*/DEBIAN) || exit 1; \
	done
	mkdir -p udeb-control
	for udeb in $(SOURCEDIR)/*.udeb; do \
		if [ -f "$$udeb" ]; then \
			name="$$(basename "$$udeb" .udeb)"; \
			dpkg-deb -e "$$udeb" "udeb-control/$$name"; \
			if [ -f "udeb-control/$$name/templates" ]; then \
				sed -n '/./,$$p' "udeb-control/$$name/templates" | \
					grep -iv '^indices.*:' >> templates; \
				echo >> templates; \
			fi; \
		fi; \
	done

clean:
	for dir in $(SOURCEDIR)/*; do \
		if [ "$${dir##*/}" != console-setup ] && [ -d "$$dir" ]; then \
			(cd "$$dir" && debian/rules clean) || exit 1; \
		fi; \
	done
	rm -f $(SOURCEDIR)/*.deb $(SOURCEDIR)/*.udeb
	rm -rf udeb-control templates

.PHONY: clean build install

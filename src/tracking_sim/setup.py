from setuptools import setup

package_name = "tracking_sim"
setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[("share/ament_index/resource_index/packages", ["resource/" + package_name]),
                ("share/" + package_name, ["package.xml"])],
    install_requires=["setuptools"],
    zip_safe=True,
    description="Scenario generation, analytic labels, Gazebo worlds and toy rendering",
    license="TBD",
)

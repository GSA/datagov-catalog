# Web proxy setup for catalog
Current setup:

```mermaid
C4Context
  title Catalog HTTP request paths
  Boundary(internet, "Internet", "the web") {
    Person(publicUser, "Public web user")
    System("openstreetmap", "tiles.openstreetmap.org", "map tiles for geo query")
    Boundary(cloud_gov_boundary, "Cloud.gov", "") {
      Boundary(datagov_boundary, "Data.gov org boundary", "") {
        Boundary(asg_public_egress, "Public egress space", "") {
        Container(datagov-catalog-proxy, "Ingress proxy", "datagov-catalog-proxy", "nginx reverse proxy", "")
	    Container(datagov-catalog, "Catalog server", "datagov-catalog", "Serves dynamic catalog pages", "")
	    }
      }
    }
  }
  Rel(publicUser, datagov-catalog-proxy, "HTTPS")
  Rel(datagov-catalog-proxy, datagov-catalog, "HTTPS")
  Rel(datagov-catalog-proxy, openstreetmap, "HTTPS", "HEAD/GET")

```

We want the space with the catalog server (and its nginx proxy) in a restricted egress space. To do that, we need to send those openmaptiles.org requests through an egress proxy.


```mermaid
C4Context
  title Catalog HTTP request paths
  Boundary(internet, "Internet", "the web") {
    Person(publicUser, "Public web user")
    System("openstreetmap", "tiles.openstreetmap.org", "map tiles for geo query")
    Boundary(cloud_gov_boundary, "Cloud.gov", "") {
      Boundary(datagov_boundary, "Data.gov org boundary", "") {

               Boundary(asg_restricted, "Restricted egress space", "") {
        Container(datagov-catalog-proxy, "Ingress proxy", "datagov-catalog-proxy", "nginx reverse proxy", "")
                Container(flask-proxy, "Flask proxy", "flask proxy", "HTTP CONNECT protocol to egress", "")
	    Container(datagov-catalog, "Catalog server", "datagov-catalog", "Serves dynamic catalog pages", "")

	    }
        Boundary(asg_public_egress, "Public egress space", "") {
	    Container(egress_proxy, "Egress (forward) proxy", "", "")
	    }
      }
    }
  }
  Rel(publicUser, datagov-catalog-proxy, "HTTPS")
  Rel(datagov-catalog-proxy, datagov-catalog, "HTTPS")
  Rel(datagov-catalog-proxy, egress_proxy, "Option 1")
  Rel(datagov-catalog, egress_proxy, "Option 2")
  Rel(datagov-catalog-proxy, flask-proxy, "HTTPS")
  Rel(flask-proxy, egress_proxy, "HTTPS")
  Rel(egress_proxy, openstreetmap, "HTTPS", "HEAD/GET")
  UpdateRelStyle(datagov-catalog-proxy, egress_proxy, $lineColor="red")
UpdateRelStyle(datagov-catalog, egress_proxy, $lineColor="red")
UpdateRelStyle(datagov-catalog-proxy, flask-proxy, $lineColor="orange")
UpdateRelStyle(flask-proxy, egress_proxy, $lineColor="orange")
UpdateLayoutConfig($c4ShapeInRow="2")
```


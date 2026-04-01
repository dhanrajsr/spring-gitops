# Spring Boot CI/CD Setup Guide

End-to-end setup for two Spring Boot applications (Maven + Gradle) with a 9-stage CI pipeline, GitOps deployment to a Kind cluster via Helm + ArgoCD, and Calico network policies.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Repository Structure](#3-repository-structure)
4. [Spring Boot Applications](#4-spring-boot-applications)
5. [Dockerfiles](#5-dockerfiles)
6. [GitHub Actions CI Pipeline](#6-github-actions-ci-pipeline)
7. [Kind Cluster with Calico](#7-kind-cluster-with-calico)
8. [GitOps Repository](#8-gitops-repository)
9. [Helm Charts](#9-helm-charts)
10. [ArgoCD Installation](#10-argocd-installation)
11. [App of Apps Pattern](#11-app-of-apps-pattern)
12. [Calico Network Policies](#12-calico-network-policies)
13. [Self-Hosted GitHub Runners](#13-self-hosted-github-runners)
14. [GitHub Secrets](#14-github-secrets)
15. [Codecov Setup](#15-codecov-setup)
16. [Verification](#16-verification)
17. [Accessing Services](#17-accessing-services)
18. [Troubleshooting](#18-troubleshooting)

---

## 1. Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Developer Push                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │  GitHub Actions │  9-stage CI pipeline
                    │  CI Pipeline    │  (build → test → quality →
                    └───────┬────────┘   security → package →
                            │            docker → push → gitops)
                            │ updates image tag
                    ┌───────▼────────┐
                    │  spring-gitops  │  GitOps repo (Helm values)
                    │  repository     │
                    └───────┬────────┘
                            │ ArgoCD detects change
                    ┌───────▼────────┐
                    │    ArgoCD       │  App of Apps pattern
                    │  (Kind cluster) │
                    └───────┬────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
      ┌───────▼───────┐         ┌─────────▼───────┐
      │    staging     │         │   production     │
      │  (auto-sync)   │         │ (manual approval)│
      └───────────────┘         └─────────────────┘
```

**Two apps:**
- `spring-maven-app` — Spring Boot with Maven, port 8080
- `spring-gradle-app` — Spring Boot with Gradle, port 8081

**Two namespaces:**
- `staging` — auto-deploys on every push to main
- `production` — requires manual approval in GitHub Environments

---

## 2. Prerequisites

Install the following on your machine:

```bash
# Java 17
brew install temurin@17

# Maven
brew install maven

# Docker Desktop
# Download from https://www.docker.com/products/docker-desktop

# Kind (Kubernetes in Docker)
brew install kind

# kubectl
brew install kubectl

# Helm
brew install helm

# GitHub CLI
brew install gh

# ArgoCD CLI
brew install argocd
```

Accounts needed:
- GitHub account
- Docker Hub account
- Codecov account (free tier at codecov.io)

---

## 3. Repository Structure

Create three repositories on GitHub:

```
github.com/<your-username>/spring-boot-app          # Maven app + CI
github.com/<your-username>/spring-boot-gradle-app   # Gradle app + CI
github.com/<your-username>/spring-gitops            # Helm charts + CD
```

---

## 4. Spring Boot Applications

### Maven App (`spring-boot-app`)

**Directory layout:**
```
spring-boot-app/
├── src/
│   ├── main/java/com/example/demo/
│   │   ├── DemoApplication.java
│   │   └── controller/HelloController.java
│   └── test/java/com/example/demo/
│       └── controller/HelloControllerTest.java
├── pom.xml
├── Dockerfile
├── codecov.yml
├── checkstyle.xml
└── .github/workflows/ci.yml
```

**`src/main/java/com/example/demo/DemoApplication.java`:**
```java
package com.example.demo;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class DemoApplication {
    public static void main(String[] args) {
        SpringApplication.run(DemoApplication.class, args);
    }
}
```

**`src/main/java/com/example/demo/controller/HelloController.java`:**
```java
package com.example.demo.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import java.util.Map;

@RestController
@RequestMapping("/api")
public class HelloController {

    @GetMapping("/hello")
    public Map<String, String> hello(@RequestParam(defaultValue = "World") String name) {
        return Map.of("message", "Hello, " + name + "!");
    }

    @GetMapping("/health")
    public Map<String, String> health() {
        return Map.of("status", "UP");
    }

    @GetMapping("/version")
    public Map<String, String> version() {
        return Map.of("version", "1.0.0", "build", "maven", "app", "spring-boot-maven");
    }
}
```

**`src/test/java/com/example/demo/controller/HelloControllerTest.java`:**
```java
package com.example.demo.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(HelloController.class)
class HelloControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Test
    void helloReturnsDefaultMessage() throws Exception {
        mockMvc.perform(get("/api/hello"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("Hello, World!"));
    }

    @Test
    void helloReturnsCustomName() throws Exception {
        mockMvc.perform(get("/api/hello").param("name", "Dhanraj"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.message").value("Hello, Dhanraj!"));
    }

    @Test
    void healthReturnsUp() throws Exception {
        mockMvc.perform(get("/api/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
    }

    @Test
    void versionReturnsInfo() throws Exception {
        mockMvc.perform(get("/api/version"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.version").value("1.0.0"))
                .andExpect(jsonPath("$.build").value("maven"))
                .andExpect(jsonPath("$.app").value("spring-boot-maven"));
    }
}
```

**`pom.xml`:**
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.4.3</version>
    <relativePath/>
  </parent>

  <groupId>com.example</groupId>
  <artifactId>demo</artifactId>
  <version>0.0.1-SNAPSHOT</version>
  <name>demo</name>

  <properties>
    <java.version>17</java.version>
    <jacoco.version>0.8.11</jacoco.version>
    <checkstyle.version>3.4.0</checkstyle.version>
    <spotbugs.version>4.8.3.1</spotbugs.version>
    <owasp.version>9.0.9</owasp.version>
    <coverage.minimum>0.80</coverage.minimum>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <!-- Spring Boot -->
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>

      <!-- JaCoCo - code coverage -->
      <plugin>
        <groupId>org.jacoco</groupId>
        <artifactId>jacoco-maven-plugin</artifactId>
        <version>${jacoco.version}</version>
        <executions>
          <execution>
            <id>prepare-agent</id>
            <goals><goal>prepare-agent</goal></goals>
          </execution>
          <execution>
            <id>report</id>
            <phase>verify</phase>
            <goals><goal>report</goal></goals>
          </execution>
          <execution>
            <id>check</id>
            <phase>verify</phase>
            <goals><goal>check</goal></goals>
            <configuration>
              <rules>
                <rule>
                  <element>BUNDLE</element>
                  <limits>
                    <limit>
                      <counter>LINE</counter>
                      <value>COVEREDRATIO</value>
                      <minimum>${coverage.minimum}</minimum>
                    </limit>
                  </limits>
                </rule>
              </rules>
            </configuration>
          </execution>
        </executions>
      </plugin>

      <!-- Checkstyle -->
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-checkstyle-plugin</artifactId>
        <version>${checkstyle.version}</version>
        <configuration>
          <configLocation>checkstyle.xml</configLocation>
          <failsOnError>true</failsOnError>
          <consoleOutput>true</consoleOutput>
        </configuration>
        <executions>
          <execution>
            <goals><goal>check</goal></goals>
          </execution>
        </executions>
      </plugin>

      <!-- SpotBugs -->
      <plugin>
        <groupId>com.github.spotbugs</groupId>
        <artifactId>spotbugs-maven-plugin</artifactId>
        <version>${spotbugs.version}</version>
        <configuration>
          <effort>Max</effort>
          <threshold>Medium</threshold>
          <failOnError>true</failOnError>
        </configuration>
      </plugin>

      <!-- OWASP Dependency Check -->
      <plugin>
        <groupId>org.owasp</groupId>
        <artifactId>dependency-check-maven</artifactId>
        <version>${owasp.version}</version>
      </plugin>
    </plugins>
  </build>
</project>
```

**`checkstyle.xml`** — place in project root:
```xml
<?xml version="1.0"?>
<!DOCTYPE module PUBLIC
  "-//Checkstyle//DTD Checkstyle Configuration 1.3//EN"
  "https://checkstyle.org/dtds/configuration_1_3.dtd">
<module name="Checker">
  <property name="severity" value="error"/>
  <module name="TreeWalker">
    <module name="UnusedImports"/>
    <module name="AvoidStarImport"/>
    <module name="WhitespaceAround"/>
    <module name="NeedBraces"/>
    <module name="EqualsHashCode"/>
    <module name="MagicNumber">
      <property name="ignoreNumbers" value="-1, 0, 1, 2"/>
    </module>
  </module>
  <module name="FileTabCharacter"/>
  <module name="NewlineAtEndOfFile"/>
</module>
```

**`codecov.yml`:**
```yaml
coverage:
  status:
    project:
      default:
        target: 80%
        threshold: 2%
    patch:
      default:
        target: 80%

parsers:
  gcov:
    branch_detection:
      conditional: yes
      loop: yes

comment:
  layout: "reach,diff,flags,files"
  behavior: default
  require_changes: false

flags:
  maven:
    paths:
      - src/main/java/
    carryforward: true
```

### Gradle App (`spring-boot-gradle-app`)

Same controller and test structure as Maven, but change the `version()` method:
```java
return Map.of("version", "1.0.0", "build", "gradle", "app", "spring-boot-gradle");
```

**`build.gradle`:**
```groovy
plugins {
    id 'org.springframework.boot' version '3.4.3'
    id 'io.spring.dependency-management' version '1.1.4'
    id 'java'
    id 'jacoco'
    id 'checkstyle'
    id 'com.github.spotbugs' version '6.0.9'
    id 'org.owasp.dependencycheck' version '9.0.9'
}

group = 'com.example'
version = '0.0.1-SNAPSHOT'
sourceCompatibility = '17'

repositories {
    mavenCentral()
}

dependencies {
    implementation 'org.springframework.boot:spring-boot-starter-web'
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
}

test {
    useJUnitPlatform()
    finalizedBy jacocoTestReport
}

jacocoTestReport {
    dependsOn test
    reports {
        xml.required = true
        html.required = true
    }
}

jacocoTestCoverageVerification {
    violationRules {
        rule {
            limit {
                counter = 'LINE'
                value = 'COVEREDRATIO'
                minimum = 0.80
            }
        }
    }
}

checkstyle {
    toolVersion = '10.12.4'
    configFile = file('checkstyle.xml')
}

spotbugs {
    effort = 'max'
    reportLevel = 'medium'
}

dependencyCheck {
    failBuildOnCVSS = 7
}

bootJar {
    archiveFileName = 'app.jar'
}
```

**`settings.gradle`:**
```groovy
rootProject.name = 'spring-gradle-app'
```

**`codecov.yml`:** Same as Maven but change the flag name:
```yaml
flags:
  gradle:          # <-- change this
    paths:
      - src/main/java/
    carryforward: true
```

**`application.properties`** (`src/main/resources/`):
```properties
server.port=8081
```

**`.gitignore`:**
```
.gradle/
build/
*.class
*.jar
```

---

## 5. Dockerfiles

**Maven `Dockerfile`:**
```dockerfile
# Stage 1: Build
FROM maven:3.9-eclipse-temurin-17 AS builder
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -q
COPY src ./src
RUN mvn clean package -DskipTests -q

# Stage 2: Run
FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

**Gradle `Dockerfile`:**
```dockerfile
# Stage 1: Build
FROM gradle:8.5-jdk17 AS builder
WORKDIR /app
COPY build.gradle settings.gradle ./
RUN gradle dependencies -q --no-daemon
COPY src ./src
RUN gradle bootJar -q --no-daemon

# Stage 2: Run
FROM eclipse-temurin:17-jre-jammy
WORKDIR /app
COPY --from=builder /app/build/libs/*.jar app.jar
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 6. GitHub Actions CI Pipeline

Both pipelines follow the same 9-stage structure. Create `.github/workflows/ci.yml` in each app repo.

### Maven CI (`spring-boot-app/.github/workflows/ci.yml`)

```yaml
name: Maven CI Pipeline

on:
  push:
    branches: [ "main", "develop" ]
  pull_request:
    branches: [ "main", "develop" ]
  workflow_dispatch:

env:
  JAVA_VERSION: '17'
  IMAGE_NAME: spring-maven-app

jobs:
  # Stage 1: Build & Compile
  build:
    name: Build & Compile
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: temurin
          cache: maven

      - name: Compile source code
        run: mvn clean compile -q

      - uses: actions/upload-artifact@v4
        with:
          name: compiled-classes
          path: target/classes
          retention-days: 1

  # Stage 2: Unit Tests & Coverage
  test:
    name: Unit Tests & Coverage
    runs-on: ubuntu-latest
    needs: build
    permissions:
      contents: read
      checks: write
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: temurin
          cache: maven

      - name: Run tests with coverage check
        run: mvn verify -q

      - name: Publish test results
        uses: dorny/test-reporter@v1
        if: always()
        with:
          name: Maven Test Results
          path: target/surefire-reports/*.xml
          reporter: java-junit

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: target/site/jacoco/jacoco.xml
          token: ${{ secrets.CODECOV_TOKEN }}
          flags: maven
          fail_ci_if_error: true

  # Stage 3: Code Quality
  code-quality:
    name: Code Quality Analysis
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: temurin
          cache: maven

      - name: Run Checkstyle
        run: mvn checkstyle:check -q

      - name: Run SpotBugs
        run: mvn spotbugs:check -q

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: spotbugs-report
          path: target/spotbugsXml.xml
          retention-days: 7

  # Stage 4: Dependency Security Scan
  dependency-security-scan:
    name: Dependency Security Scan (OWASP)
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: temurin
          cache: maven

      - name: OWASP Dependency Check
        run: |
          mvn org.owasp:dependency-check-maven:check \
            -DfailBuildOnCVSS=7 \
            --no-transfer-progress || true

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: owasp-report
          path: target/dependency-check-report.html
          retention-days: 7

  # Stage 5: Package JAR
  package:
    name: Package Application
    runs-on: ubuntu-latest
    needs: [ test, code-quality ]
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-java@v4
        with:
          java-version: ${{ env.JAVA_VERSION }}
          distribution: temurin
          cache: maven

      - name: Build JAR
        run: mvn clean package -DskipTests -q

      - uses: actions/upload-artifact@v4
        with:
          name: app-jar
          path: target/*.jar
          retention-days: 7

  # Stage 6: Docker Build & Security Scan
  docker-build-scan:
    name: Docker Build & Security Scan
    runs-on: ubuntu-latest
    needs: package
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-buildx-action@v3

      - name: Build Docker image
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          outputs: type=docker,dest=/tmp/image.tar
      - run: docker load --input /tmp/image.tar

      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          format: table
          exit-code: 1
          ignore-unfixed: true
          severity: CRITICAL

      - uses: actions/upload-artifact@v4
        with:
          name: docker-image
          path: /tmp/image.tar
          retention-days: 1

  # Stage 7: Push to Docker Hub (main only)
  docker-push:
    name: Push Docker Image to Docker Hub
    runs-on: ubuntu-latest
    needs: docker-build-scan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: docker-image
          path: /tmp
      - run: docker load --input /tmp/image.tar

      - uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Tag and push
        run: |
          docker tag ${{ env.IMAGE_NAME }}:${{ github.sha }} \
            ${{ secrets.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          docker tag ${{ env.IMAGE_NAME }}:${{ github.sha }} \
            ${{ secrets.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:latest
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
          docker push ${{ secrets.DOCKERHUB_USERNAME }}/${{ env.IMAGE_NAME }}:latest

  # Stage 8: Update GitOps repo → ArgoCD deploys to staging
  deploy-staging:
    name: Update GitOps Repo → ArgoCD deploys to Staging
    runs-on: ubuntu-latest
    needs: docker-push
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment:
      name: staging
      url: http://localhost:30080
    steps:
      - uses: actions/checkout@v4
        with:
          repository: <your-username>/spring-gitops
          token: ${{ secrets.GITOPS_TOKEN }}
          path: spring-gitops

      - name: Update image tag
        run: |
          sed -i "s/tag:.*/tag: ${{ github.sha }}/" \
            spring-gitops/apps/spring-maven/helm/values.yaml

      - name: Commit and push
        run: |
          cd spring-gitops
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add apps/spring-maven/helm/values.yaml
          git commit -m "ci(spring-maven): update image tag to ${{ github.sha }}"
          git push

  # Stage 9: Production approval gate
  deploy-production:
    name: Approve → ArgoCD syncs Production
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    environment:
      name: production
      url: http://localhost:30090
    steps:
      - run: |
          echo "Staging deployed with tag: ${{ github.sha }}"
          echo "Go to ArgoCD UI and approve production sync."
```

### Gradle CI (`spring-boot-gradle-app/.github/workflows/ci.yml`)

Same structure as Maven. Key differences:

| Setting | Maven | Gradle |
|---------|-------|--------|
| `IMAGE_NAME` | `spring-maven-app` | `spring-gradle-app` |
| `cache:` | `maven` | `gradle` |
| compile step | `mvn clean compile -q` | `./gradlew classes --no-daemon -q` |
| test step | `mvn verify -q` | `./gradlew test jacocoTestReport jacocoTestCoverageVerification --no-daemon -q` |
| test results path | `target/surefire-reports/*.xml` | `build/test-results/test/*.xml` |
| coverage path | `target/site/jacoco/jacoco.xml` | `build/reports/jacoco/test/jacocoTestReport.xml` |
| Codecov flags | `maven` | `gradle` |
| checkstyle | `mvn checkstyle:check -q` | `./gradlew checkstyleMain --no-daemon -q` |
| spotbugs | `mvn spotbugs:check -q` | `./gradlew spotbugsMain --no-daemon -q` |
| package | `mvn clean package -DskipTests -q` | `./gradlew bootJar --no-daemon -q` |
| jar path | `target/*.jar` | `build/libs/*.jar` |
| GitOps path | `apps/spring-maven/helm/values.yaml` | `apps/spring-gradle/helm/values.yaml` |
| gitops commit msg | `ci(spring-maven)` | `ci(spring-gradle)` |
| staging NodePort URL | `30080` | `30081` |
| production NodePort URL | `30090` | `30091` |

Also add `chmod +x gradlew` before every Gradle step:
```yaml
- name: Grant execute permission to Gradle wrapper
  run: chmod +x gradlew
```

---

## 7. Kind Cluster with Calico

### Create Kind config with Calico

```yaml
# kind-calico.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  disableDefaultCNI: true    # disable kindnet, use Calico instead
  podSubnet: "192.168.0.0/16"
nodes:
  - role: control-plane
  - role: worker
  - role: worker
  - role: worker
```

```bash
kind create cluster --name calico-prod --config kind-calico.yaml
```

### Install Calico

```bash
# Install Calico operator
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/tigera-operator.yaml

# Install Calico custom resources
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.27.0/manifests/custom-resources.yaml

# Wait for Calico to be ready (takes ~2 minutes)
kubectl wait --for=condition=Ready pods --all -n calico-system --timeout=300s
```

### Verify cluster

```bash
kubectl get nodes
# All nodes should show Ready
```

---

## 8. GitOps Repository

Create `spring-gitops` repository with this structure:

```
spring-gitops/
├── argocd/
│   ├── app-of-apps.yaml
│   ├── spring-maven-staging.yaml
│   ├── spring-maven-production.yaml
│   ├── spring-gradle-staging.yaml
│   └── spring-gradle-production.yaml
├── apps/
│   ├── spring-maven/
│   │   └── helm/
│   │       ├── Chart.yaml
│   │       ├── values.yaml
│   │       ├── values-staging.yaml
│   │       ├── values-production.yaml
│   │       └── templates/
│   │           ├── deployment.yaml
│   │           └── service.yaml
│   └── spring-gradle/
│       └── helm/
│           ├── Chart.yaml
│           ├── values.yaml
│           ├── values-staging.yaml
│           ├── values-production.yaml
│           └── templates/
│               ├── deployment.yaml
│               └── service.yaml
├── network-policies/
│   ├── staging-isolation.yaml
│   └── production-isolation.yaml
└── .github/workflows/cd.yml
```

---

## 9. Helm Charts

### `apps/spring-maven/helm/Chart.yaml`

```yaml
apiVersion: v2
name: spring-maven-app
description: Spring Boot Maven Application
type: application
version: 1.0.0
appVersion: "1.0.0"
```

### `apps/spring-maven/helm/values.yaml`

```yaml
image:
  repository: <your-dockerhub-username>/spring-maven-app
  tag: latest          # CI overwrites this with the git SHA on every push
  pullPolicy: Always

replicaCount: 1

service:
  type: ClusterIP
  port: 8080
  targetPort: 8080

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi

livenessProbe:
  path: /api/health
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  path: /api/health
  initialDelaySeconds: 20
  periodSeconds: 5
```

### `apps/spring-maven/helm/values-staging.yaml`

```yaml
replicaCount: 1

service:
  type: NodePort
  nodePort: 30080
```

### `apps/spring-maven/helm/values-production.yaml`

```yaml
replicaCount: 2

service:
  type: NodePort
  nodePort: 30090
```

### `apps/spring-maven/helm/templates/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ .Release.Name }}
    version: {{ .Values.image.tag | quote }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
        version: {{ .Values.image.tag | quote }}
    spec:
      containers:
        - name: {{ .Release.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: {{ .Values.service.targetPort }}
          livenessProbe:
            httpGet:
              path: {{ .Values.livenessProbe.path }}
              port: {{ .Values.service.targetPort }}
            initialDelaySeconds: {{ .Values.livenessProbe.initialDelaySeconds }}
            periodSeconds: {{ .Values.livenessProbe.periodSeconds }}
          readinessProbe:
            httpGet:
              path: {{ .Values.readinessProbe.path }}
              port: {{ .Values.service.targetPort }}
            initialDelaySeconds: {{ .Values.readinessProbe.initialDelaySeconds }}
            periodSeconds: {{ .Values.readinessProbe.periodSeconds }}
          resources:
            requests:
              cpu: {{ .Values.resources.requests.cpu }}
              memory: {{ .Values.resources.requests.memory }}
            limits:
              cpu: {{ .Values.resources.limits.cpu }}
              memory: {{ .Values.resources.limits.memory }}
```

### `apps/spring-maven/helm/templates/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}
  namespace: {{ .Release.Namespace }}
  labels:
    app: {{ .Release.Name }}
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      {{- if eq .Values.service.type "NodePort" }}
      nodePort: {{ .Values.service.nodePort }}
      {{- end }}
```

> For the Gradle chart, use the same templates. In `values.yaml` change `repository` to `spring-gradle-app`, `port`/`targetPort` to `8081`. In `values-staging.yaml` set `nodePort: 30081`. In `values-production.yaml` set `nodePort: 30091`.

---

## 10. ArgoCD Installation

```bash
# Create namespace and install ArgoCD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for ArgoCD to be ready
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s

# Expose ArgoCD as NodePort (for UI access via port-forward on macOS)
kubectl patch svc argocd-server -n argocd \
  -p '{"spec": {"type": "NodePort"}}'

# Enable apiKey capability for the admin account (needed for API tokens)
kubectl patch configmap argocd-cm -n argocd --type merge \
  -p '{"data":{"accounts.admin":"apiKey,login"}}'

# Get the initial admin password
kubectl get secret argocd-initial-admin-secret -n argocd \
  -o jsonpath='{.data.password}' | base64 -d && echo

# Access the UI (run in a separate terminal and open https://localhost:8443)
kubectl port-forward svc/argocd-server -n argocd 8443:443
```

### Generate an API token (for CD pipeline)

```bash
# Login via CLI
argocd login localhost:8443 --username admin --insecure

# Generate token
argocd account generate-token --account admin
# Copy the output — this is your ARGOCD_ADMIN_PASSWORD secret
```

---

## 11. App of Apps Pattern

### `argocd/app-of-apps.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: spring-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-username>/spring-gitops.git
    targetRevision: main
    path: argocd
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### `argocd/spring-maven-staging.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: spring-maven-staging
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-username>/spring-gitops.git
    targetRevision: main
    path: apps/spring-maven/helm
    helm:
      valueFiles:
        - values.yaml
        - values-staging.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: staging
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

### `argocd/spring-maven-production.yaml`

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: spring-maven-production
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-username>/spring-gitops.git
    targetRevision: main
    path: apps/spring-maven/helm
    helm:
      valueFiles:
        - values.yaml
        - values-production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: production
  syncPolicy:
    syncOptions:
      - CreateNamespace=true
    # No automated sync — manual approval required
```

> Create identical files for `spring-gradle-staging.yaml` and `spring-gradle-production.yaml` replacing `spring-maven` with `spring-gradle` throughout.

### Bootstrap ArgoCD (one-time only)

```bash
# Apply the root app — ArgoCD then creates all child apps automatically
kubectl apply -f argocd/app-of-apps.yaml

# Also apply network policies manually (not managed by ArgoCD)
kubectl apply -f network-policies/staging-isolation.yaml
kubectl apply -f network-policies/production-isolation.yaml
```

---

## 12. Calico Network Policies

### `network-policies/staging-isolation.yaml`

```yaml
apiVersion: crd.projectcalico.org/v1
kind: NetworkPolicy
metadata:
  name: staging-isolation
  namespace: staging
spec:
  selector: all()
  ingress:
    - action: Allow
      source:
        namespaceSelector: projectcalico.org/name == 'staging'
    - action: Allow
      source:
        namespaceSelector: projectcalico.org/name == 'kube-system'
    - action: Allow
      source:
        namespaceSelector: projectcalico.org/name == 'argocd'
    - action: Deny
  egress:
    - action: Allow
```

### `network-policies/production-isolation.yaml`

```yaml
apiVersion: crd.projectcalico.org/v1
kind: NetworkPolicy
metadata:
  name: production-isolation
  namespace: production
spec:
  selector: all()
  ingress:
    - action: Allow
      source:
        namespaceSelector: projectcalico.org/name == 'production'
    - action: Allow
      source:
        namespaceSelector: projectcalico.org/name == 'kube-system'
    - action: Allow
      source:
        namespaceSelector: projectcalico.org/name == 'argocd'
    - action: Deny
  egress:
    - action: Allow
```

> Note: Use `crd.projectcalico.org/v1` — NOT `projectcalico.org/v3` which does not exist.

---

## 13. Self-Hosted GitHub Runners

You need two self-hosted runners on your MacBook — one for each app repo and one for the GitOps repo.

### Register runners

Go to each repository → Settings → Actions → Runners → New self-hosted runner.

For each runner, download and configure:

```bash
# Create a directory for the runner
mkdir ~/actions-runner-<repo-name> && cd ~/actions-runner-<repo-name>

# Download (macOS ARM64)
curl -o actions-runner-osx-arm64.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.x.x/actions-runner-osx-arm64-2.x.x.tar.gz
tar xzf actions-runner-osx-arm64.tar.gz

# Configure (get the token from GitHub UI)
./config.sh --url https://github.com/<your-username>/<repo-name> \
  --token <TOKEN_FROM_GITHUB> \
  --labels self-hosted,docker,linux,macos \
  --name runner-<repo-name>

# Start the runner (keep this terminal open, or install as a service)
./run.sh
```

> The CD pipeline (`spring-gitops`) uses `runs-on: [self-hosted, docker, linux]` so use those labels.

---

## 14. GitHub Secrets

Set these secrets in each repository (Settings → Secrets and variables → Actions):

### `spring-boot-app` and `spring-boot-gradle-app`

| Secret | Value |
|--------|-------|
| `DOCKERHUB_USERNAME` | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Docker Hub access token (generate at hub.docker.com → Account Settings → Security) |
| `CODECOV_TOKEN` | From codecov.io → repository settings |
| `GITOPS_TOKEN` | GitHub PAT with `repo` scope — used to push to spring-gitops |

### `spring-gitops`

| Secret | Value |
|--------|-------|
| `ARGOCD_ADMIN_PASSWORD` | ArgoCD API token generated in Step 10 |

### Set secrets via GitHub CLI

```bash
gh secret set DOCKERHUB_USERNAME --body "<value>" -R <your-username>/spring-boot-app
gh secret set DOCKERHUB_TOKEN    --body "<value>" -R <your-username>/spring-boot-app
gh secret set CODECOV_TOKEN      --body "<value>" -R <your-username>/spring-boot-app
gh secret set GITOPS_TOKEN       --body "<value>" -R <your-username>/spring-boot-app

# Repeat for spring-boot-gradle-app

gh secret set ARGOCD_ADMIN_PASSWORD --body "<token>" -R <your-username>/spring-gitops
```

### GitHub Environment setup

Go to each app repo → Settings → Environments and create:

- `staging` — no protection rules (auto-deploys)
- `production` — add Required reviewers (yourself) for manual approval gate

---

## 15. Codecov Setup

1. Go to [codecov.io](https://codecov.io) and sign in with GitHub
2. Add both repositories
3. Copy the upload token from each repo's settings
4. Set as `CODECOV_TOKEN` secret in the corresponding GitHub repo
5. The `codecov.yml` in each repo configures the 80% coverage threshold and flags the language correctly as Java

---

## 16. CD Pipeline (`spring-gitops/.github/workflows/cd.yml`)

```yaml
name: GitOps CD Pipeline

on:
  push:
    branches: [ "main" ]
  workflow_dispatch:

jobs:
  # Stage 1: Validate Helm Charts
  helm-validate:
    name: Validate Helm Charts
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/setup-helm@v4
      - name: Lint spring-maven
        run: |
          helm lint apps/spring-maven/helm \
            -f apps/spring-maven/helm/values.yaml \
            -f apps/spring-maven/helm/values-staging.yaml
          helm lint apps/spring-maven/helm \
            -f apps/spring-maven/helm/values.yaml \
            -f apps/spring-maven/helm/values-production.yaml
      - name: Lint spring-gradle
        run: |
          helm lint apps/spring-gradle/helm \
            -f apps/spring-gradle/helm/values.yaml \
            -f apps/spring-gradle/helm/values-staging.yaml
          helm lint apps/spring-gradle/helm \
            -f apps/spring-gradle/helm/values.yaml \
            -f apps/spring-gradle/helm/values-production.yaml
      - name: Template render spring-maven staging
        run: |
          helm template spring-maven-staging apps/spring-maven/helm \
            -f apps/spring-maven/helm/values.yaml \
            -f apps/spring-maven/helm/values-staging.yaml \
            --namespace staging
      - name: Template render spring-maven production
        run: |
          helm template spring-maven-production apps/spring-maven/helm \
            -f apps/spring-maven/helm/values.yaml \
            -f apps/spring-maven/helm/values-production.yaml \
            --namespace production
      - name: Template render spring-gradle staging
        run: |
          helm template spring-gradle-staging apps/spring-gradle/helm \
            -f apps/spring-gradle/helm/values.yaml \
            -f apps/spring-gradle/helm/values-staging.yaml \
            --namespace staging
      - name: Template render spring-gradle production
        run: |
          helm template spring-gradle-production apps/spring-gradle/helm \
            -f apps/spring-gradle/helm/values.yaml \
            -f apps/spring-gradle/helm/values-production.yaml \
            --namespace production

  # Stage 2: Wait for staging to be healthy
  sync-staging:
    name: ArgoCD Wait — Staging Healthy
    runs-on: [self-hosted, docker, linux]
    needs: helm-validate
    steps:
      - name: Wait for spring-maven staging Synced
        run: |
          kubectl wait app/spring-maven-staging -n argocd \
            --for=jsonpath='{.status.sync.status}'=Synced --timeout=180s
      - name: Wait for spring-maven staging Healthy
        run: |
          kubectl wait app/spring-maven-staging -n argocd \
            --for=jsonpath='{.status.health.status}'=Healthy --timeout=180s
      - name: Wait for spring-gradle staging Synced
        run: |
          kubectl wait app/spring-gradle-staging -n argocd \
            --for=jsonpath='{.status.sync.status}'=Synced --timeout=180s
      - name: Wait for spring-gradle staging Healthy
        run: |
          kubectl wait app/spring-gradle-staging -n argocd \
            --for=jsonpath='{.status.health.status}'=Healthy --timeout=180s

  # Stage 3: Manual approval → sync production
  sync-production:
    name: Approve → ArgoCD Sync Production
    runs-on: [self-hosted, docker, linux]
    needs: sync-staging
    environment:
      name: production
      url: http://localhost:30090
    steps:
      - name: Trigger spring-maven production sync
        run: |
          kubectl patch app spring-maven-production -n argocd --type=merge \
            -p '{"operation": {"initiatedBy": {"username": "cd-pipeline"}, "sync": {}}}'
      - name: Wait for spring-maven production Synced
        run: |
          kubectl wait app/spring-maven-production -n argocd \
            --for=jsonpath='{.status.sync.status}'=Synced --timeout=120s
      - name: Wait for spring-maven production Healthy
        run: |
          kubectl wait app/spring-maven-production -n argocd \
            --for=jsonpath='{.status.health.status}'=Healthy --timeout=120s
      - name: Trigger spring-gradle production sync
        run: |
          kubectl patch app spring-gradle-production -n argocd --type=merge \
            -p '{"operation": {"initiatedBy": {"username": "cd-pipeline"}, "sync": {}}}'
      - name: Wait for spring-gradle production Synced
        run: |
          kubectl wait app/spring-gradle-production -n argocd \
            --for=jsonpath='{.status.sync.status}'=Synced --timeout=120s
      - name: Wait for spring-gradle production Healthy
        run: |
          kubectl wait app/spring-gradle-production -n argocd \
            --for=jsonpath='{.status.health.status}'=Healthy --timeout=120s
```

> The `sync-staging` and `sync-production` jobs run on `[self-hosted, docker, linux]` because they need `kubectl` access to the local Kind cluster.

---

## 17. Verification

After completing all steps, verify:

```bash
# Cluster nodes
kubectl get nodes

# ArgoCD apps
kubectl get applications -n argocd

# Staging pods
kubectl get pods -n staging

# Production pods
kubectl get pods -n production

# Services
kubectl get svc -n staging
kubectl get svc -n production

# Network policies
kubectl get networkpolicies -n staging
kubectl get networkpolicies -n production
```

---

## 18. Accessing Services

Since Kind on macOS does not map NodePorts to localhost, use `kubectl port-forward`:

```bash
# Staging
kubectl port-forward svc/spring-maven-staging 8080:8080 -n staging
kubectl port-forward svc/spring-gradle-staging 8081:8081 -n staging

# Production
kubectl port-forward svc/spring-maven-production 9080:8080 -n production
kubectl port-forward svc/spring-gradle-production 9081:8081 -n production

# ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8443:443
```

| Service | URL |
|---------|-----|
| Maven Staging | http://localhost:8080/api/hello |
| Gradle Staging | http://localhost:8081/api/hello |
| Maven Production | http://localhost:9080/api/hello |
| Gradle Production | http://localhost:9081/api/hello |
| ArgoCD UI | https://localhost:8443 (admin / `<initial-password>`) |

Other endpoints: `/api/health`, `/api/version`, `/api/hello?name=YourName`

---

## 19. Troubleshooting

### Pod stuck in ContainerCreating

Calico CNI token expired on a worker node.

```bash
# Find which node the pod is on
kubectl get pod <pod-name> -n <namespace> -o jsonpath='{.spec.nodeName}'

# Find and restart the calico-node pod on that node
NODE=<node-name>
kubectl delete pod -n kube-system \
  $(kubectl get pod -n kube-system -l k8s-app=calico-node -o wide \
    | grep $NODE | awk '{print $1}')

# Delete the stuck pod so it reschedules
kubectl delete pod <pod-name> -n <namespace>
```

### ArgoCD app stuck OutOfSync

```bash
# Trigger sync manually via kubectl
kubectl patch app <app-name> -n argocd --type=merge \
  -p '{"operation": {"initiatedBy": {"username": "manual"}, "sync": {}}}'
```

### Staging app not auto-syncing

Check that the CI pipeline updated the image tag in the GitOps repo:
```bash
cat apps/spring-maven/helm/values.yaml | grep tag
```

Check ArgoCD app status:
```bash
kubectl get application spring-maven-staging -n argocd -o jsonpath='{.status.sync.status}'
```

### Docker Hub login failing

Regenerate your Docker Hub access token at hub.docker.com → Account Settings → Security → New Access Token, then update the secret:
```bash
gh secret set DOCKERHUB_TOKEN --body "<new-token>" -R <your-username>/spring-boot-app
```

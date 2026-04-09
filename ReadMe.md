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
19. [CD Pipeline](#19-cd-pipeline)
20. [ApplicationSet Pattern (Pattern 3)](#20-applicationset-pattern-pattern-3)
21. [Adding a New Application — Recommended Order](#21-adding-a-new-application--recommended-order)
22. [Blue-Green Deployment (spring-maven)](#22-blue-green-deployment-spring-maven)
23. [Canary Deployment (spring-gradle)](#23-canary-deployment-spring-gradle)
24. [Blue-Green Rollback Scenarios](#24-blue-green-rollback-scenarios)
25. [ArgoCD on EKS — Production Setup](#25-argocd-on-eks--production-setup)
    - [Configure kubectl for EKS](#step-1--configure-kubectl-for-eks)
    - [Install ArgoCD on EKS](#step-2--install-argocd-on-eks)
    - [Expose ArgoCD UI via LoadBalancer](#step-3--expose-argocd-ui)
    - [Install Argo Rollouts](#step-4--install-argo-rollouts-on-eks)
    - [Deploy Applications](#step-5--deploy-applications-via-argocd)
    - [Blue-Green on EKS with real DNS](#step-7--blue-green-deployment-on-eks-production)
    - [Monitor Rollout Status](#step-8--monitor-rollout-status)
    - [Key Commands Reference](#argocd-key-commands-reference)
    - [Kind vs EKS Differences](#difference-kind-cluster-vs-eks)
    - [Troubleshooting](#troubleshooting-argocd-on-eks)
26. [Onboarding a New Application to GitOps](#26-onboarding-a-new-application-to-gitops)
    - [What Is Manual vs Automatic](#what-is-manual-vs-automatic)
    - [Step 1 — Create Helm Chart](#step-1--create-helm-chart-in-spring-gitops)
    - [Step 2 — Create ArgoCD Manifests](#step-2--create-argocd-application-manifests)
    - [Step 3 — Register with ArgoCD](#step-3--register-apps-with-argocd-once)
    - [Step 4 — Add CI GitOps Update Step](#step-4--add-gitops-update-step-to-app-ci-pipeline)
    - [Full Lifecycle After Setup](#full-lifecycle-after-setup)
    - [Onboarding Checklist](#checklist--new-application-onboarding)
27. [HPA and KEDA — Autoscaling Setup](#27-hpa-and-keda--autoscaling-setup)
    - [Prerequisites — Metrics Server + KEDA install](#prerequisites)
    - [HPA Configuration](#hpa-configuration)
    - [KEDA Scalers — HTTP, SQS, Cron](#keda-configuration)
    - [HPA + KEDA with Blue-Green](#hpa--keda-with-blue-green-argo-rollouts)
    - [Environment Strategy](#environment-strategy)
    - [Troubleshooting](#troubleshooting-1)

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
### Pattern1: (Small environment less than 50 Applications)

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

---

## 20. ApplicationSet Pattern (Pattern 3)

Instead of maintaining one ArgoCD `Application` file per app per environment, this repo uses **ApplicationSet** — a single file that generates all Application resources automatically from a list of app names.

### How it works

```
argocd/
├── app-of-apps.yaml                 # bootstraps everything (applied once via kubectl)
├── applicationset-staging.yaml      # generates: spring-maven-staging, spring-gradle-staging
└── applicationset-production.yaml   # generates: spring-maven-production, spring-gradle-production
```

The App of Apps watches the `argocd/` folder. When it syncs, it creates both ApplicationSets. Each ApplicationSet iterates over its `elements` list and generates one ArgoCD `Application` per entry.

### Why two ApplicationSets instead of one

Staging and production require different sync policies:
- **Staging** — `automated: prune: true, selfHeal: true` (deploys immediately on git change)
- **Production** — no `automated` block (manual approval required)

ArgoCD ApplicationSet templates must be valid YAML before goTemplate processing, so conditional blocks like `{{- if .autoSync }}` cannot be used to toggle the `automated` section. Two files with hardcoded policies is the standard industry approach.

### applicationset-staging.yaml

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: spring-apps-staging
  namespace: argocd
spec:
  goTemplate: true
  goTemplateOptions: ["missingkey=error"]
  generators:
    - list:
        elements:
          - app: spring-maven
          - app: spring-gradle
  template:
    metadata:
      name: "{{.app}}-staging"
      namespace: argocd
    spec:
      project: default
      source:
        repoURL: https://github.com/<your-username>/spring-gitops.git
        targetRevision: main
        path: "apps/{{.app}}/helm"
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

### applicationset-production.yaml

Same structure as staging but:
- `name: "{{.app}}-production"`
- `valueFiles` includes `values-production.yaml`
- `namespace: production`
- No `automated` block under `syncPolicy`

### Adding a new app to an existing cluster

To add `node-js-app`, append one line to the `elements` list in **both** files:

```yaml
  generators:
    - list:
        elements:
          - app: spring-maven
          - app: spring-gradle
          - app: node-js-app      # ← add this
```

ArgoCD automatically generates `node-js-app-staging` and `node-js-app-production` Applications pointing to `apps/node-js-app/helm`.

---

## 21. Adding a New Application — Recommended Order

Follow this order to avoid ArgoCD showing a `Missing` / `Unknown` health state.

### Why order matters

If you add the app to the ApplicationSet before the Docker image exists, ArgoCD creates the Application immediately but the deployment fails because the image tag in `values.yaml` does not exist on Docker Hub yet. The app shows `Missing` health until the image is pushed.

### Correct order

**Step 1 — Create the application repository**

Create the new repo (e.g. `node-js-app`) on GitHub with:
- Application source code
- CI pipeline (`.github/workflows/ci.yml`)
- `Dockerfile`
- Set all required secrets: `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `CODECOV_TOKEN`, `GITOPS_TOKEN`

**Step 2 — Push to main and let CI run**

Push a commit to `main`. The CI pipeline must complete successfully through to the Docker push stage so the image exists on Docker Hub with a real SHA tag.

**Step 3 — Add the Helm chart to spring-gitops**

Create the Helm chart directory in spring-gitops:

```
apps/node-js-app/helm/
├── Chart.yaml
├── values.yaml          ← set image.repository and initial image.tag to the SHA from Step 2
├── values-staging.yaml  ← set service.type: NodePort and nodePort
├── values-production.yaml
└── templates/
    ├── deployment.yaml
    └── service.yaml
```

**Step 4 — Add the app to both ApplicationSets**

In `argocd/applicationset-staging.yaml` and `argocd/applicationset-production.yaml`, add the new app name to the `elements` list.

**Step 5 — Commit and push spring-gitops**

```bash
git add apps/node-js-app/ argocd/applicationset-staging.yaml argocd/applicationset-production.yaml
git commit -m "feat: add node-js-app to cluster"
git push
```

ArgoCD detects the change → creates `node-js-app-staging` and `node-js-app-production` → immediately deploys because the image already exists → goes straight to `Healthy`.

**Step 6 — Add the GitOps update step to the CI pipeline**

In the new app's CI pipeline, add the deploy-staging job that updates the image tag in spring-gitops on every push to main:

```yaml
deploy-staging:
  steps:
    - uses: actions/checkout@v4
      with:
        repository: <your-username>/spring-gitops
        token: ${{ secrets.GITOPS_TOKEN }}
        path: spring-gitops
    - run: |
        sed -i "s/tag:.*/tag: ${{ github.sha }}/" \
          spring-gitops/apps/node-js-app/helm/values.yaml
    - run: |
        cd spring-gitops
        git config user.name "github-actions[bot]"
        git config user.email "github-actions[bot]@users.noreply.github.com"
        git add apps/node-js-app/helm/values.yaml
        git commit -m "ci(node-js-app): update image tag to ${{ github.sha }}"
        git push
```

### Summary

| Step | Where | What |
|------|-------|------|
| 1 | New app repo | Create repo, CI pipeline, Dockerfile, secrets |
| 2 | GitHub Actions | Push to main → image built and pushed to Docker Hub |
| 3 | spring-gitops | Add `apps/node-js-app/helm/` with initial image tag |
| 4 | spring-gitops | Append `node-js-app` to both ApplicationSet elements |
| 5 | spring-gitops | Commit and push → ArgoCD deploys immediately |
| 6 | New app repo | Add GitOps update step to CI pipeline |
```

---

## 22. Blue-Green Deployment (spring-maven)

### Overview

Blue-Green deployment runs two full environments simultaneously:
- **Blue** — the current stable version receiving all live traffic
- **Green** — the new version deployed alongside blue, receiving no traffic until promoted

Traffic switches **instantly** from blue to green on promotion — zero downtime, instant rollback by switching back.

```
New image pushed
      │
      ▼
ArgoCD detects new tag → creates Green ReplicaSet
      │
      ▼
Green pods pass health checks → Rollout pauses (BlueGreenPause)
      │
      ▼
Manual promotion → traffic switches Blue → Green instantly
      │
      ▼
Old Blue pods scale down after 30 seconds
```

### Tool

**Argo Rollouts** — replaces the standard Kubernetes `Deployment` with a `Rollout` CRD.

### Install Argo Rollouts

```bash
# Install controller
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts \
  -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# Install kubectl plugin (macOS)
brew install argoproj/tap/kubectl-argo-rollouts
```

### Helm Chart Changes

**`apps/spring-maven/helm/templates/rollout.yaml`** — replaces `deployment.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: {{ .Release.Name }}
  namespace: {{ .Release.Namespace }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    # ... same pod spec as Deployment ...
  strategy:
    blueGreen:
      activeService: {{ .Release.Name }}          # blue — live traffic
      previewService: {{ .Release.Name }}-preview  # green — new version
      autoPromotionEnabled: false                  # manual promotion required
      scaleDownDelaySeconds: 30                    # keep blue 30s after promotion
```

**`apps/spring-maven/helm/templates/service-preview.yaml`** — green preview service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-preview
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      nodePort: {{ .Values.service.previewNodePort }}
```

**`values-staging.yaml`:**
```yaml
service:
  type: NodePort
  nodePort: 30080         # active (blue)
  previewNodePort: 30082  # preview (green)
```

**`values-production.yaml`:**
```yaml
service:
  type: NodePort
  nodePort: 30090         # active (blue)
  previewNodePort: 30092  # preview (green)
```

**`values.yaml`** — add blue-green config:
```yaml
blueGreen:
  autoPromotionEnabled: false
  scaleDownDelaySeconds: 30
```

### How to Trigger

Push any code change to `spring-boot-app` main branch. CI builds a new image, updates the tag in `spring-gitops/apps/spring-maven/helm/values.yaml`, and ArgoCD automatically creates the green ReplicaSet.

### Validation Steps

**Step 1 — Start port-forwards in separate terminals:**

```bash
# Terminal 1 — Active (Blue)
kubectl port-forward svc/spring-maven-staging -n staging 8080:8080

# Terminal 2 — Preview (Green)
kubectl port-forward svc/spring-maven-staging-preview -n staging 8082:8080
```

**Step 2 — Confirm two versions running simultaneously:**

```bash
curl http://localhost:8080/api/version   # Blue → old version (e.g. 1.0.0)
curl http://localhost:8082/api/version   # Green → new version (e.g. 1.1.0)
```

This proves blue and green are live at the same time with different versions.

**Step 3 — Confirm live traffic only goes to Blue:**

```bash
for i in {1..5}; do curl -s http://localhost:8080/api/version; echo; done
# All responses return old version — green is running but gets no live traffic
```

**Step 4 — Promote Green to Active:**

```bash
kubectl argo rollouts promote spring-maven-staging -n staging
```

**Step 5 — Confirm traffic switched instantly:**

```bash
# Restart port-forward first (stale connections don't follow selector changes)
# Ctrl+C Terminal 1, then:
kubectl port-forward svc/spring-maven-staging -n staging 8080:8080

curl http://localhost:8080/api/version   # Now returns new version (1.1.0)
```

Same URL, same port — traffic switched with zero downtime.

**Step 6 — Confirm old Blue cleaned up:**

```bash
# After 30 seconds (scaleDownDelaySeconds)
kubectl get pods -n staging -l app=spring-maven-staging
# Only 1 pod remains (the green/new one)
```

**Step 7 — Rollback (optional):**

Before promoting, run:
```bash
kubectl argo rollouts abort spring-maven-staging -n staging
curl http://localhost:8080/api/version   # Still returns old version — blue unchanged
```

### Watch Live Progress

```bash
kubectl get rollout spring-maven-staging -n staging -o wide -w
```

### Key Commands

| Action | Command |
|--------|---------|
| Check status | `kubectl get rollout spring-maven-staging -n staging` |
| Promote green | `kubectl argo rollouts promote spring-maven-staging -n staging` |
| Abort rollback | `kubectl argo rollouts abort spring-maven-staging -n staging` |
| Watch progress | `kubectl get rollout spring-maven-staging -n staging -w` |

---

## 23. Canary Deployment (spring-gradle)

### Overview

Canary deployment gradually shifts traffic from the old version to the new version in configurable steps — allowing validation at each step before proceeding.

```
New image pushed
      │
      ▼
ArgoCD detects new tag → creates Canary pods
      │
      ▼
Step 1: 20% traffic → new version  (manual pause)
      │  ← validate here
      ▼
Step 2: 50% traffic → new version  (auto-resumes after 30s)
      │
      ▼
Step 3: 100% traffic → new version (rollout complete)
```

### Two Approaches

#### Approach 1 — Pod-based (approximate weight)

Traffic split is determined by the ratio of canary to stable pods:
- `setWeight: 20` with 5 replicas → 1 canary pod ≈ 20%
- Approximate — depends on having enough replicas

#### Approach 2 — NGINX Ingress-based (exact weight) ← what we use

Argo Rollouts sets exact traffic weights via NGINX ingress annotations:
```
nginx.ingress.kubernetes.io/canary-weight: "20"
```
Exactly 20% regardless of replica count.

### Install NGINX Ingress (Kind)

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
kubectl wait --for=condition=Ready pods -n ingress-nginx \
  -l app.kubernetes.io/component=controller --timeout=120s
```

### Helm Chart Changes

**`apps/spring-gradle/helm/templates/service.yaml`** — two services instead of one:

```yaml
# Stable service — receives traffic from old (stable) pods
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-stable
spec:
  type: ClusterIP
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
---
# Canary service — receives traffic from new (canary) pods
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-canary
spec:
  type: ClusterIP
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
```

**`apps/spring-gradle/helm/templates/ingress.yaml`:**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  ingressClassName: nginx
  rules:
    - host: {{ .Values.ingress.host }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ .Release.Name }}-stable
                port:
                  number: {{ .Values.service.port }}
```

**`apps/spring-gradle/helm/templates/rollout.yaml`:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  strategy:
    canary:
      stableService: {{ .Release.Name }}-stable
      canaryService: {{ .Release.Name }}-canary
      trafficRouting:
        nginx:
          stableIngress: {{ .Release.Name }}   # NGINX controls exact weight
      steps:
        - setWeight: 20        # Step 1: exactly 20% → canary
        - pause: {}            # Step 2: manual pause
        - setWeight: 50        # Step 3: exactly 50% → canary
        - pause:
            duration: 30       # Step 4: auto-resume after 30s
        - setWeight: 100       # Step 5: 100% → canary (complete)
```

**`values-staging.yaml`:**
```yaml
replicaCount: 2
service:
  type: ClusterIP
ingress:
  host: spring-gradle.staging.local
```

### Network Policy

Allow NGINX ingress namespace in Calico policy (both staging and production):

```yaml
- action: Allow
  source:
    namespaceSelector: projectcalico.org/name == 'ingress-nginx'
```

### /etc/hosts Setup (one-time)

```bash
echo "127.0.0.1 spring-gradle.staging.local" | sudo tee -a /etc/hosts
echo "127.0.0.1 spring-gradle.production.local" | sudo tee -a /etc/hosts
```

### How to Trigger

Push any code change to `spring-boot-gradle-app` main branch. CI builds a new image and updates the tag in `spring-gitops/apps/spring-gradle/helm/values.yaml`. ArgoCD deploys canary pods and pauses at Step 1 (20%).

### Validation Steps

**Step 1 — Port-forward NGINX ingress:**

```bash
kubectl port-forward svc/ingress-nginx-controller -n ingress-nginx 8081:80
```

**Step 2 — Confirm stable version before rollout:**

```bash
curl http://spring-gradle.staging.local:8081/api/version
# Returns current stable version (e.g. 1.0.0)
```

**Step 3 — Trigger new deploy, then confirm 20% canary weight:**

```bash
# Check NGINX annotation set by Argo Rollouts
kubectl get ingress -n staging
# Two ingresses: spring-gradle-staging (stable) and spring-gradle-staging-canary (auto-created)

kubectl get ingress spring-gradle-staging-spring-gradle-staging-canary \
  -n staging -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}'
# → 20
```

**Step 4 — Verify traffic split at 20%:**

```bash
for i in {1..20}; do curl -s http://spring-gradle.staging.local:8081/api/version | grep version; echo; done
# ~4 responses with new version (20%), ~16 with old version (80%)
# This is exact — not pod-ratio approximation
```

**Step 5 — Resume to 50% (manual promotion):**

```bash
kubectl argo rollouts promote spring-gradle-staging -n staging
```

Verify weight updated:
```bash
kubectl get ingress spring-gradle-staging-spring-gradle-staging-canary \
  -n staging -o jsonpath='{.metadata.annotations.nginx\.ingress\.kubernetes\.io/canary-weight}'
# → 50
```

```bash
for i in {1..20}; do curl -s http://spring-gradle.staging.local:8081/api/version | grep version; echo; done
# ~10 each version (50/50 split)
```

**Step 6 — Auto-promotes to 100% after 30 seconds:**

```bash
for i in {1..10}; do curl -s http://spring-gradle.staging.local:8081/api/version | grep version; echo; done
# All responses return new version
```

**Step 7 — Rollback at any step (optional):**

```bash
kubectl argo rollouts abort spring-gradle-staging -n staging
for i in {1..10}; do curl -s http://spring-gradle.staging.local:8081/api/version | grep version; echo; done
# All responses instantly return stable version
```

### Key Commands

| Action | Command |
|--------|---------|
| Check status | `kubectl get rollout spring-gradle-staging -n staging` |
| Resume/promote | `kubectl argo rollouts promote spring-gradle-staging -n staging` |
| Abort rollback | `kubectl argo rollouts abort spring-gradle-staging -n staging` |
| Watch progress | `kubectl get rollout spring-gradle-staging -n staging -w` |
| Check canary weight | `kubectl get ingress -n staging -o yaml \| grep canary-weight` |

### Difference from Blue-Green

| | Blue-Green | Canary |
|--|--|--|
| Traffic switch | Instant (all at once) | Gradual (step by step) |
| Old version during deploy | Runs alongside new | Runs alongside new |
| Rollback speed | Instant | Instant (abort) |
| Validation window | Before promotion | At each weight step |
| Services needed | 2 (active + preview) | 2 (stable + canary) |
| Ingress needed | No | Yes (for exact weights) |
| Best for | High-risk changes needing instant cutover | Gradual validation with real traffic |

---

## 24. Blue-Green Rollback Scenarios

There are three rollback scenarios depending on when something goes wrong.

---

### Scenario 1 — Green pods fail health checks (automatic)

If the green pods crash or fail readiness/liveness probes, Argo Rollouts automatically aborts the rollout. **Blue stays active throughout — no traffic is ever sent to the broken green.**

```
Green pods fail health checks
      │
      ▼
Argo Rollouts detects failure → auto-aborts rollout
      │
      ▼
Green pods scale down (after abortScaleDownDelaySeconds: 30s)
      │
      ▼
Blue continues serving traffic — zero impact to users
```

**How to verify this happened:**
```bash
kubectl get rollout spring-maven-staging -n staging
# Status: ✖ Degraded  (or Paused with error message)

kubectl get rollout spring-maven-staging -n staging \
  -o jsonpath='{.status.message}'
# → "RolloutAborted: Rollout aborted update to revision X"
```

**To retry with a fixed image:**
```bash
# Push a new fixed image via CI — ArgoCD detects new tag and starts fresh rollout
# OR manually update the image tag:
kubectl argo rollouts set image spring-maven-staging \
  spring-maven-staging=dhanrajsubbaianind/spring-maven-app:<fixed-tag> \
  -n staging
```

---

### Scenario 2 — Green is healthy but you want to rollback before promoting (manual abort)

Green passed health checks, rollout is paused waiting for your approval — but you decide to not promote (e.g. you tested the preview URL and found a bug).

```bash
# Abort — green scales down, blue stays active
kubectl argo rollouts abort spring-maven-staging -n staging
```

**Verify blue is still serving:**
```bash
curl http://localhost:8080/api/version   # Returns old stable version
```

**Verify green is gone:**
```bash
kubectl get pods -n staging -l app=spring-maven-staging
# Only 1 pod (blue) remains
```

---

### Scenario 3 — Something went wrong AFTER promotion (post-promotion rollback)

You promoted green, traffic switched to green, but now you're seeing errors. Blue pods are still alive for `scaleDownDelaySeconds: 30` seconds after promotion — use this window.

**Within 30 seconds of promotion:**
```bash
# Undo — switches active service back to blue instantly
kubectl argo rollouts undo spring-maven-staging -n staging
```

**After 30 seconds (blue already scaled down):**
```bash
# Roll back to previous revision
kubectl argo rollouts undo spring-maven-staging -n staging
# Argo Rollouts creates a new rollout using the previous stable image
```

**Verify rollback completed:**
```bash
kubectl get rollout spring-maven-staging -n staging
# Status: ✔ Healthy  with previous image tag

curl http://localhost:8080/api/version   # Returns previous version
```

---

### Rollback Config Reference

```yaml
blueGreen:
  autoPromotionEnabled: false     # never auto-promote — always require manual approval
  scaleDownDelaySeconds: 30       # keep blue pods 30s after promotion for post-promotion rollback
  previewReplicaCount: 1          # number of green pods to run during preview
  abortScaleDownDelaySeconds: 30  # grace period before cleaning up failed green pods
```

| Config | Purpose |
|--------|---------|
| `autoPromotionEnabled: false` | Blue never loses traffic without explicit human approval |
| `scaleDownDelaySeconds: 30` | Post-promotion rollback window — blue stays alive 30s |
| `previewReplicaCount: 1` | Limits green to 1 pod during preview (saves resources) |
| `abortScaleDownDelaySeconds: 30` | Grace period for green cleanup on abort/failure |

---

### Summary — When Does Blue Stay Safe?

| Scenario | Blue traffic affected? | Action needed |
|----------|----------------------|---------------|
| Green pods crash/fail probes | No — auto-aborted | Push fix via CI |
| Green healthy, you abort before promoting | No | `kubectl argo rollouts abort` |
| Post-promotion issue (within 30s) | Yes — switch back | `kubectl argo rollouts undo` |
| Post-promotion issue (after 30s) | Yes — new rollout from old image | `kubectl argo rollouts undo` |

---

## 25. ArgoCD on EKS — Production Setup

This section covers deploying and using ArgoCD on the actual AWS EKS cluster (`eks-dev-us-east-1`), as opposed to the local Kind cluster used in earlier sections.

---

### Prerequisites

- EKS cluster provisioned (`aws-eks` Terraform apply completed)
- `kubectl` and `aws` CLI installed locally
- Cluster access configured (see below)

---

### Step 1 — Configure kubectl for EKS

```bash
# Update kubeconfig to point to EKS cluster
aws eks update-kubeconfig --region us-east-1 --name eks-dev-us-east-1

# Verify cluster access
kubectl get nodes
# Expected: ip-10-0-x-x.ec2.internal   Ready   <none>   ...
```

**If you get "server has asked for credentials" error:**
```bash
# Grant your IAM identity cluster admin access
aws eks create-access-entry \
  --cluster-name eks-dev-us-east-1 \
  --principal-arn arn:aws:iam::497041484428:root \
  --type STANDARD

aws eks associate-access-policy \
  --cluster-name eks-dev-us-east-1 \
  --principal-arn arn:aws:iam::497041484428:root \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster

# Retry
kubectl get nodes
```

---

### Step 2 — Install ArgoCD on EKS

```bash
# Create namespace
kubectl create namespace argocd

# Download and apply manifest (avoids pipe encoding issues)
curl -sL https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml \
  -o /tmp/argocd-install.yaml
kubectl apply -n argocd -f /tmp/argocd-install.yaml

# Wait for all pods to be running
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s

# Verify
kubectl get pods -n argocd
# Expected: argocd-server, argocd-application-controller, argocd-repo-server,
#           argocd-redis, argocd-dex-server, argocd-applicationset-controller — all Running
```

---

### Step 3 — Expose ArgoCD UI

On EKS, expose ArgoCD via AWS LoadBalancer (not NodePort like Kind):

```bash
# Patch to LoadBalancer type — AWS auto-provisions an ALB/NLB
kubectl patch svc argocd-server -n argocd \
  -p '{"spec": {"type": "LoadBalancer"}}'

# Wait ~60s for ELB to provision, then get the URL
kubectl get svc argocd-server -n argocd
# EXTERNAL-IP column shows: xxxx.us-east-1.elb.amazonaws.com

# Get the initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o go-template='{{.data.password | base64decode}}' && echo
```

**Access the UI:**
- URL: `https://<elb-hostname>` (accept self-signed cert warning in browser)
- Username: `admin`
- Password: output of command above

> Change the password after first login: ArgoCD UI → User Info → Update Password

---

### Step 4 — Install Argo Rollouts on EKS

Argo Rollouts is the controller that handles Blue-Green and Canary strategies:

```bash
# Create namespace
kubectl create namespace argo-rollouts

# Download and apply manifest
curl -sL https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml \
  -o /tmp/argo-rollouts-install.yaml
kubectl apply -n argo-rollouts -f /tmp/argo-rollouts-install.yaml

# Verify
kubectl get pods -n argo-rollouts
# Expected: argo-rollouts-xxxx   Running

# Install kubectl plugin (macOS) — gives you 'kubectl argo rollouts' commands
brew install argoproj/tap/kubectl-argo-rollouts
```

---

### Step 5 — Deploy Applications via ArgoCD

```bash
# Create app namespaces
kubectl create namespace staging
kubectl create namespace production

# Apply ArgoCD Application manifests from this repo
kubectl apply -f argocd/spring-maven-staging.yaml
kubectl apply -f argocd/spring-maven-production.yaml
kubectl apply -f argocd/spring-gradle-staging.yaml
kubectl apply -f argocd/spring-gradle-production.yaml

# Verify apps appear in ArgoCD
kubectl get applications -n argocd
```

In the **ArgoCD UI**:
- You'll see 4 applications: `spring-maven-staging`, `spring-maven-production`, `spring-gradle-staging`, `spring-gradle-production`
- Staging apps: **auto-sync** on every Git push
- Production apps: **manual sync** — you click Sync in the UI

---

### Step 6 — Sync an Application

**Via UI:**
1. Open ArgoCD UI → click `spring-maven-production`
2. Click **Sync** → **Synchronize**
3. Watch pods come up in real time in the UI

**Via CLI:**
```bash
# Login to ArgoCD CLI
argocd login <elb-hostname> --username admin --password <password> --insecure

# Sync app
argocd app sync spring-maven-production

# Check app status
argocd app get spring-maven-production
```

---

### Step 7 — Blue-Green Deployment on EKS (Production)

Unlike Kind (port-forward), on EKS traffic is served via real DNS and ALB Ingress.

**The two URLs (production namespace):**

| URL | Service | Version served |
|---|---|---|
| `spring-maven.devopscab.com` | `spring-maven` (active) | Blue — live users |
| `spring-maven-preview.devopscab.com` | `spring-maven-preview` | Green — testing only |

**Full deployment cycle:**

```
1. Developer pushes code to spring-boot-maven-app
         ↓
2. CI pipeline: build → test → docker push → update values.yaml image tag → push to spring-gitops
         ↓
3. ArgoCD detects new image tag in spring-gitops → marks app OutOfSync
         ↓
4. ArgoCD syncs → Argo Rollouts creates Green ReplicaSet (v2)
   Blue (v1) still serves 100% traffic on spring-maven.devopscab.com
         ↓
5. Green pods pass liveness/readiness probes → Rollout pauses at BlueGreenPause
   Green available on: spring-maven-preview.devopscab.com
         ↓
6. QA tests the preview URL (v2) — users unaffected on production URL
         ↓
7. Approve → Promote Green to active
         ↓
8. Traffic switches instantly: spring-maven.devopscab.com now serves v2
   Blue (v1) pods stay alive for 30s (rollback window)
         ↓
9. After 30s — Blue pods removed. Rollout complete.
```

**Promote Green to production:**
```bash
# CLI
kubectl argo rollouts promote spring-maven -n production

# Watch live
kubectl argo rollouts get rollout spring-maven -n production --watch
```

**Rollback before promotion (Green failed testing):**
```bash
kubectl argo rollouts abort spring-maven -n production
# Blue continues serving traffic — Green pods removed
```

**Rollback after promotion (within 30s — Blue still alive):**
```bash
kubectl argo rollouts undo spring-maven -n production
# Traffic switches back to Blue instantly
```

---

### Step 8 — Monitor Rollout Status

```bash
# Summary view
kubectl argo rollouts get rollout spring-maven -n production

# Live watch (updates every second)
kubectl argo rollouts get rollout spring-maven -n production --watch

# Check all rollouts across namespaces
kubectl get rollouts -A

# Describe rollout for events and history
kubectl describe rollout spring-maven -n production
```

**In ArgoCD UI:**
- Click the app → you'll see the Rollout resource
- It shows: Blue ReplicaSet (stable), Green ReplicaSet (canary/preview), Pause status
- Click **Promote** button directly in the UI

---

### Step 9 — Connect ArgoCD to GitHub (Private Repos)

If your repos are private, add credentials so ArgoCD can pull manifests:

```bash
# Via CLI
argocd repo add https://github.com/dhanrajsr/spring-gitops.git \
  --username dhanrajsr \
  --password <github-pat-token>

# Verify
argocd repo list
```

Or via **UI**: Settings → Repositories → Connect Repo

---

### ArgoCD Key Commands Reference

| Action | Command |
|---|---|
| List all apps | `argocd app list` |
| Sync app | `argocd app sync <app-name>` |
| Get app status | `argocd app get <app-name>` |
| Check diff (what will change) | `argocd app diff <app-name>` |
| Hard refresh (bypass cache) | `argocd app get <app-name> --hard-refresh` |
| Delete app | `argocd app delete <app-name>` |
| Promote Blue-Green | `kubectl argo rollouts promote <rollout-name> -n <namespace>` |
| Abort (keep Blue) | `kubectl argo rollouts abort <rollout-name> -n <namespace>` |
| Undo (rollback) | `kubectl argo rollouts undo <rollout-name> -n <namespace>` |
| Watch rollout | `kubectl argo rollouts get rollout <name> -n <namespace> --watch` |
| Pause rollout | `kubectl argo rollouts pause <rollout-name> -n <namespace>` |
| Restart rollout | `kubectl argo rollouts restart <rollout-name> -n <namespace>` |

---

### Difference: Kind Cluster vs EKS

| | Kind (local) | EKS (production) |
|---|---|---|
| Access ArgoCD UI | `kubectl port-forward` + `localhost:8443` | LoadBalancer ELB URL |
| App traffic | `kubectl port-forward` or NodePort | ALB Ingress + Route53 DNS |
| Preview URL | `localhost:8082` | `spring-maven-preview.devopscab.com` |
| Image pull | Docker Hub (public) | Docker Hub or ECR |
| State | Ephemeral (lost on Mac restart) | Persistent (AWS managed) |
| Cost | Free | ~$0.10/hr for EKS control plane + EC2 nodes |

---

### Troubleshooting ArgoCD on EKS

| Symptom | Likely cause | Fix |
|---|---|---|
| App stuck `OutOfSync` after sync | Helm render error | `argocd app get <name>` → check conditions |
| `ComparisonError` | ArgoCD can't reach git repo | Add repo credentials in ArgoCD Settings |
| Rollout stuck at `Paused` | Waiting for manual promotion | `kubectl argo rollouts promote <name> -n <ns>` |
| Green pods not starting | Image pull error or probe failure | `kubectl describe pod <green-pod> -n production` |
| ArgoCD UI not accessible | ELB still provisioning | Wait 60–90s after `kubectl patch svc` |
| `ImagePullBackOff` on Green | Wrong image tag in values.yaml | Fix tag in spring-gitops → ArgoCD re-syncs |
| Old Blue pods not scaling down | `scaleDownDelaySeconds` in progress | Wait 30s — or check `kubectl get rs -n production` |

---

## 26. Onboarding a New Application to GitOps

When you build a brand new application and want to deploy it via ArgoCD + Blue-Green, the **Helm chart and ArgoCD manifests must be created manually once**. After that, CI takes over automatically on every build.

---

### What Is Manual vs Automatic

```
NEW APPLICATION — one-time manual setup required:

  Developer creates new app repo (e.g. school-api)
        │
        ▼ ── MANUAL (done once) ──────────────────────────────
  1. Create Helm chart folder in spring-gitops
  2. Create ArgoCD Application manifests in spring-gitops
  3. Register apps with ArgoCD (kubectl apply)
  4. Add gitops update step to the app's CI pipeline
        │
        ▼ ── AUTOMATIC (every push from this point on) ───────
  5. Developer pushes code → CI builds image → updates image
     tag in values.yaml → pushes to spring-gitops → ArgoCD
     detects change → deploys new Green version automatically
```

**Why it can't be fully automatic:**
The CI pipeline only updates a values.yaml that already exists. It has no logic to create a new app folder from scratch. Someone must create the Helm chart and register the app with ArgoCD once.

---

### Step 1 — Create Helm Chart in spring-gitops

Create the following folder structure in the `spring-gitops` repo:

```
apps/<app-name>/helm/
├── Chart.yaml
├── values.yaml               ← image tag lives here — CI updates this
├── values-staging.yaml       ← staging-specific overrides
├── values-production.yaml    ← production overrides + preview host URL
└── templates/
    ├── rollout.yaml          ← Blue-Green Rollout (replaces Deployment)
    ├── service.yaml          ← active service (Blue — production traffic)
    ├── service-preview.yaml  ← preview service (Green — testing only)
    └── ingress.yaml          ← ALB Ingress with active + preview hosts
```

**`Chart.yaml`** — chart metadata:
```yaml
apiVersion: v2
name: <app-name>
description: Helm chart for <app-name>
type: application
version: 1.0.0
appVersion: "1.0.0"
```

**`values.yaml`** — base config (CI updates `image.tag` here):
```yaml
image:
  repository: <dockerhub-username>/<app-name>
  tag: latest          # CI replaces this on every build
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
  initialDelaySeconds: 60
  periodSeconds: 10

readinessProbe:
  path: /api/health
  initialDelaySeconds: 45
  periodSeconds: 5

ingress:
  host: <app-name>.devopscab.com
  previewHost: ""
  certificateArn: arn:aws:acm:us-east-1:497041484428:certificate/<cert-id>

blueGreen:
  autoPromotionEnabled: false    # always require manual promotion
  scaleDownDelaySeconds: 30      # keep Blue 30s after promotion
  previewReplicaCount: 1         # Green runs 1 pod during testing
  abortScaleDownDelaySeconds: 30
```

**`values-staging.yaml`** — staging overrides:
```yaml
replicaCount: 1

ingress:
  host: <app-name>-staging.devopscab.com
  previewHost: ""
```

**`values-production.yaml`** — production overrides:
```yaml
replicaCount: 2

ingress:
  host: <app-name>.devopscab.com
  previewHost: <app-name>-preview.devopscab.com  # Green preview URL
```

---

**`templates/rollout.yaml`** — Blue-Green Rollout:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: {{ .Release.Name }}
  namespace: {{ .Release.Namespace }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}
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
  strategy:
    blueGreen:
      activeService: {{ .Release.Name }}          # Blue — live traffic
      previewService: {{ .Release.Name }}-preview  # Green — testing only
      autoPromotionEnabled: {{ .Values.blueGreen.autoPromotionEnabled }}
      scaleDownDelaySeconds: {{ .Values.blueGreen.scaleDownDelaySeconds }}
      previewReplicaCount: {{ .Values.blueGreen.previewReplicaCount }}
      abortScaleDownDelaySeconds: {{ .Values.blueGreen.abortScaleDownDelaySeconds }}
```

**`templates/service.yaml`** — active (Blue) service:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}
  namespace: {{ .Release.Namespace }}
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
```

**`templates/service-preview.yaml`** — preview (Green) service:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Release.Name }}-preview
  namespace: {{ .Release.Namespace }}
spec:
  type: {{ .Values.service.type }}
  selector:
    app: {{ .Release.Name }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
```

**`templates/ingress.yaml`** — ALB Ingress with active + preview hosts:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ .Release.Name }}
  namespace: {{ .Release.Namespace }}
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/certificate-arn: {{ .Values.ingress.certificateArn }}
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}]'
spec:
  rules:
    - host: {{ .Values.ingress.host }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ .Release.Name }}
                port:
                  number: {{ .Values.service.port }}
    {{- if .Values.ingress.previewHost }}
    - host: {{ .Values.ingress.previewHost }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ .Release.Name }}-preview
                port:
                  number: {{ .Values.service.port }}
    {{- end }}
```

---

### Step 2 — Create ArgoCD Application Manifests

Create two files in the `argocd/` folder of `spring-gitops`:

**`argocd/<app-name>-staging.yaml`** — auto-deploys on every push:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <app-name>-staging
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/dhanrajsr/spring-gitops.git
    targetRevision: main
    path: apps/<app-name>/helm
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

**`argocd/<app-name>-production.yaml`** — manual promotion required:
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <app-name>-production
  namespace: argocd
  annotations:
    argocd.argoproj.io/sync-wave: "2"
spec:
  project: default
  source:
    repoURL: https://github.com/dhanrajsr/spring-gitops.git
    targetRevision: main
    path: apps/<app-name>/helm
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
    # No automated sync — manual approval required in ArgoCD UI
```

---

### Step 3 — Register Apps with ArgoCD (Once)

```bash
kubectl apply -f argocd/<app-name>-staging.yaml
kubectl apply -f argocd/<app-name>-production.yaml

# Verify they appear in ArgoCD
kubectl get applications -n argocd
```

In the ArgoCD UI you will now see the new apps. Click **Sync** on staging to deploy the first version.

---

### Step 4 — Add GitOps Update Step to App CI Pipeline

In the app's GitHub Actions CI workflow (e.g. `.github/workflows/ci.yml`), add this step after the Docker push step:

```yaml
- name: Checkout spring-gitops repo
  uses: actions/checkout@v4
  with:
    repository: dhanrajsr/spring-gitops
    token: ${{ secrets.GITOPS_PAT }}
    path: spring-gitops

- name: Update image tag in GitOps repo
  run: |
    sed -i "s/tag:.*/tag: ${{ github.sha }}/" \
      spring-gitops/apps/<app-name>/helm/values.yaml
    cd spring-gitops
    git config user.name "github-actions"
    git config user.email "github-actions@github.com"
    git add apps/<app-name>/helm/values.yaml
    git commit -m "ci(<app-name>): update image tag to ${{ github.sha }}"
    git push
```

> **Secret required:** `GITOPS_PAT` — a GitHub Personal Access Token with `repo` scope, set in the app repo's secrets.
> ```bash
> gh secret set GITOPS_PAT --body "<pat-token>" --repo dhanrajsr/<app-name>
> ```

---

### Full Lifecycle After Setup

Once Steps 1–4 are done, this happens automatically on every code push:

```
Developer pushes code
        ↓
CI: build → test → docker push (new image)
        ↓
CI: update apps/<app-name>/helm/values.yaml (image.tag = <sha>)
        ↓
CI: git push to spring-gitops
        ↓
ArgoCD: detects values.yaml changed → marks app OutOfSync
        ↓
Staging: auto-syncs → Green pods deploy → Blue-Green promotion
         happens automatically (autoPromotionEnabled: true for staging)
        ↓
Production: shows OutOfSync in UI → you click Sync → Green deploys
            → you test preview URL → you click Promote → traffic switches
```

---

### Checklist — New Application Onboarding

```
□ Create apps/<app-name>/helm/Chart.yaml
□ Create apps/<app-name>/helm/values.yaml
□ Create apps/<app-name>/helm/values-staging.yaml
□ Create apps/<app-name>/helm/values-production.yaml
□ Create apps/<app-name>/helm/templates/rollout.yaml
□ Create apps/<app-name>/helm/templates/service.yaml
□ Create apps/<app-name>/helm/templates/service-preview.yaml
□ Create apps/<app-name>/helm/templates/ingress.yaml
□ Create argocd/<app-name>-staging.yaml
□ Create argocd/<app-name>-production.yaml
□ kubectl apply -f argocd/<app-name>-staging.yaml
□ kubectl apply -f argocd/<app-name>-production.yaml
□ Add gitops update step to app CI pipeline
□ Set GITOPS_PAT secret in app repo
□ Push a commit → verify ArgoCD detects and deploys
```

---

## 27. HPA and KEDA — Autoscaling Setup

---

### Overview

Without autoscaling, `replicaCount` is a fixed number — pods never increase under load. This section adds two layers of autoscaling:

| | HPA | KEDA |
|---|---|---|
| Full name | Horizontal Pod Autoscaler | Kubernetes Event Driven Autoscaling |
| Built into Kubernetes | Yes | No — installed separately |
| Scale trigger | CPU / Memory | HTTP requests, SQS queue, Cron, Kafka, etc. |
| Scale to zero | No (min 1) | Yes — can scale to 0 pods |
| Best for | General compute load | Event queues, scheduled spikes, HTTP traffic |
| Works with Argo Rollouts | Yes — targets Rollout resource | Yes — targets Rollout resource |

**Important:** When KEDA is enabled, it creates its own internal HPA. You should use either HPA or KEDA per app — not both simultaneously, unless you use `transfer-hpa-ownership` annotation (already added in templates).

---

### Prerequisites

#### 1. Install Metrics Server (required for HPA)

HPA reads CPU/Memory from the Metrics Server. EKS does not install it by default.

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Verify
kubectl get deployment metrics-server -n kube-system
kubectl top nodes    # should show CPU/Memory usage
kubectl top pods -n production
```

#### 2. Install KEDA

```bash
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

helm install keda kedacore/keda \
  --namespace keda \
  --create-namespace \
  --wait

# Verify
kubectl get pods -n keda
# Expected: keda-operator and keda-operator-metrics-apiserver — Running
```

#### 3. Install KEDA HTTP Add-on (for HTTP scaler)

The built-in KEDA HTTP scaler requires the HTTP add-on:

```bash
helm install http-add-on kedacore/keda-add-ons-http \
  --namespace keda \
  --wait

# Verify
kubectl get pods -n keda | grep http
```

---

### What Was Added to Helm Charts

Two new templates added to both `spring-maven` and `spring-gradle`:

```
apps/<app>/helm/templates/
├── hpa.yaml           ← HPA targeting Argo Rollout (CPU/Memory)
└── scaledobject.yaml  ← KEDA ScaledObject (HTTP / SQS / Cron)
```

Both are **disabled by default** in `values.yaml` and **enabled in `values-production.yaml`**.

---

### HPA Configuration

**How it works:**
```
Metrics Server reads pod CPU/Memory every 15s
        ↓
HPA compares actual usage vs target (e.g. 70% CPU)
        ↓
If usage > target → add pods (up to maxReplicas)
If usage < target → remove pods (down to minReplicas)
        ↓
Scale-up: fast (30s stabilization, 2 pods at a time)
Scale-down: slow (180s stabilization, 1 pod at a time) — avoids flapping
```

**Config in `values.yaml` (disabled) / `values-production.yaml` (enabled):**
```yaml
hpa:
  enabled: true
  minReplicas: 2          # never go below 2 in production
  maxReplicas: 10         # never exceed 10
  targetCPUUtilization: 70     # scale up when avg CPU > 70%
  targetMemoryUtilization: 80  # scale up when avg Memory > 80%
```

**Verify HPA is working:**
```bash
kubectl get hpa -n production
# NAME            REFERENCE                    TARGETS         MINPODS   MAXPODS   REPLICAS
# spring-maven    Rollout/spring-maven         45%/70%         2         10        2

kubectl describe hpa spring-maven -n production
# Shows scaling events, current/desired replicas, conditions
```

**Load test to trigger HPA:**
```bash
# Install hey (HTTP load generator)
brew install hey

# Hit the app with 200 concurrent requests
hey -n 10000 -c 200 https://spring-maven.devopscab.com/api/health

# Watch HPA react in real time
kubectl get hpa spring-maven -n production -w
```

---

### KEDA Configuration

KEDA supports multiple scalers — you can enable any combination in `values-production.yaml`.

#### Scaler 1 — HTTP Request Rate

Scales based on requests per second hitting the app.

```yaml
keda:
  enabled: true
  http:
    enabled: true
    hosts:
      - spring-maven.devopscab.com
    targetRequestsPerSecond: "100"  # 1 pod per 100 req/sec
```

Example: If 350 req/sec → scales to 4 pods. If drops to 50 req/sec → scales back to 1.

#### Scaler 2 — AWS SQS Queue

Scales based on messages waiting in an SQS queue. Ideal for async job processing.

```yaml
keda:
  enabled: true
  sqs:
    enabled: true
    queueURL: https://sqs.us-east-1.amazonaws.com/497041484428/my-queue
    targetQueueLength: "10"   # 1 pod per 10 messages
    region: us-east-1
```

Example: Queue has 50 messages → scales to 5 pods. Queue empty → scales to 0 pods.

> **IAM required:** Pod needs `sqs:GetQueueAttributes` permission via IRSA.

#### Scaler 3 — Cron (Scheduled Scaling)

Pre-scales to a fixed replica count on a schedule — before expected traffic spikes.

```yaml
keda:
  enabled: true
  cron:
    enabled: true
    timezone: Asia/Kolkata
    start: "0 8 * * 1-5"     # Mon-Fri 8am IST → scale up
    end: "0 20 * * 1-5"      # Mon-Fri 8pm IST → scale down
    desiredReplicas: "3"      # run 3 pods during business hours
```

**Verify KEDA ScaledObject:**
```bash
kubectl get scaledobject -n production
# NAME            SCALETARGETKIND   SCALETARGETNAME   MIN   MAX   READY   ACTIVE
# spring-maven    Rollout           spring-maven       2     10    True    True

kubectl describe scaledobject spring-maven -n production
```

---

### HPA + KEDA with Blue-Green (Argo Rollouts)

Both HPA and KEDA target the **Rollout** resource (not a Deployment). During a Blue-Green deployment:

```
Blue-Green promotion in progress:
  Blue Rollout  ← HPA/KEDA managing this (active)
  Green Rollout ← previewReplicaCount: 1 (fixed during testing)

After promotion:
  Green becomes active → HPA/KEDA immediately manages the new active ReplicaSet
  Blue scales down after scaleDownDelaySeconds (30s)
```

The autoscaler seamlessly follows the active ReplicaSet through promotions — no manual intervention needed.

---

### Environment Strategy

| Environment | HPA | KEDA | Min Replicas | Max Replicas |
|---|---|---|---|---|
| Staging | Disabled | Disabled | 1 (fixed) | 1 (fixed) |
| Production | Enabled | Enabled (HTTP + Cron) | 2 | 10 |

Staging uses fixed replicas to save cost and keep deployments predictable. Production uses both HPA and KEDA.

---

### Scaling Decision Flow

```
Traffic hits spring-maven.devopscab.com
        │
        ├── KEDA HTTP scaler checks req/sec every 30s
        │     > 100 req/sec → requests more replicas
        │
        ├── HPA checks CPU/Memory every 15s
        │     > 70% CPU → requests more replicas
        │
        └── Kubernetes scheduler picks the higher replica count
              and adds/removes pods accordingly
```

---

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| HPA shows `<unknown>/70%` for targets | Metrics Server not installed | `kubectl apply -f metrics-server manifest` |
| HPA not scaling up | CPU requests not set in pod spec | Ensure `resources.requests.cpu` is set in values.yaml |
| KEDA ScaledObject shows `READY: False` | KEDA operator not running | `kubectl get pods -n keda` |
| HTTP scaler not working | HTTP add-on not installed | `helm install http-add-on kedacore/keda-add-ons-http -n keda` |
| SQS scaler auth error | Pod missing IAM permissions | Add `sqs:GetQueueAttributes` to pod's IAM role via IRSA |
| Pods not scaling during Blue-Green | HPA targeting wrong resource | Confirm `scaleTargetRef.kind: Rollout` in hpa.yaml |
| Scale-down too aggressive | Default stabilization too short | Increase `scaleDown.stabilizationWindowSeconds` in hpa.yaml |
